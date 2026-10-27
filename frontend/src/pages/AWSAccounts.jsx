// src/pages/AWSAccounts.jsx
import { useState } from 'react'
import { useDashboard, useAddAWSAccount, useRemoveAWSAccount, useGenerateExternalId } from '../hooks/useDashboard'
import { PageHeader, LoadingPage, ErrorState, EmptyState, Modal, AlertBanner, SectionTitle } from '../components/ui'
import { format } from 'date-fns'

export default function AWSAccounts() {
  const { data, isLoading, isError, refetch } = useDashboard()
  const addAccount    = useAddAWSAccount()
  const removeAccount = useRemoveAWSAccount()
  const genExtId      = useGenerateExternalId()

  const [showAdd, setShowAdd] = useState(false)
  const [step, setStep]       = useState(1)   // 1 = generate ID, 2 = enter role ARN
  const [extIdData, setExtIdData] = useState(null)
  const [form, setForm]       = useState({ account_id: '', account_name: '', role_arn: '', external_id: '' })
  const [removeId, setRemoveId]   = useState(null)
  const [error, setError]     = useState('')

  if (isLoading) return <LoadingPage />
  if (isError)   return <ErrorState message="Failed to load accounts." onRetry={refetch} />

  const accounts = data?.aws_accounts ?? []
  const plan     = data?.customer?.plan ?? 'starter'
  const limits   = { starter: 1, growth: 3, business: 10 }
  const limit    = limits[plan] ?? 1
  const canAdd   = accounts.length < limit

  const handleOpenAdd = async () => {
    setStep(1); setError(''); setShowAdd(true)
    const result = await genExtId.mutateAsync()
    setExtIdData(result)
    setForm((f) => ({ ...f, external_id: result.external_id }))
  }

  const handleSubmit = async () => {
    setError('')
    if (!form.account_id || !form.role_arn || !form.external_id) {
      setError('All fields are required.')
      return
    }
    if (!form.role_arn.startsWith('arn:aws:iam::')) {
      setError('Role ARN must start with arn:aws:iam::')
      return
    }
    try {
      await addAccount.mutateAsync(form)
      setShowAdd(false)
      setForm({ account_id: '', account_name: '', role_arn: '', external_id: '' })
    } catch (e) {
      setError(e.response?.data?.detail ?? 'Failed to add account. Please check your Role ARN.')
    }
  }

  const handleRemove = async () => {
    await removeAccount.mutateAsync(removeId)
    setRemoveId(null)
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="AWS Accounts"
        subtitle={`${accounts.length} of ${limit} accounts connected (${plan} plan)`}
        action={
          canAdd ? (
            <button className="btn-primary" onClick={handleOpenAdd}>
              + Connect account
            </button>
          ) : (
            <a href="/billing" className="btn-primary">Upgrade to add more</a>
          )
        }
      />

      {accounts.length === 0 ? (
        <EmptyState
          icon="☁"
          title="No AWS accounts connected"
          description="Connect your first AWS account to start monitoring costs and finding idle resources."
          action={<button className="btn-primary" onClick={handleOpenAdd}>Connect first account</button>}
        />
      ) : (
        <div className="card p-0 overflow-hidden">
          <div className="divide-y divide-gray-50">
            {accounts.map((acc) => (
              <div key={acc.id} className="flex items-center gap-4 px-5 py-4">
                <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${acc.sync_error ? 'bg-red-400' : 'bg-green-400'}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900">{acc.name ?? acc.account_id}</span>
                    <span className="font-mono text-xs text-gray-400 bg-gray-50 px-2 py-0.5 rounded">{acc.account_id}</span>
                  </div>
                  {acc.sync_error ? (
                    <p className="text-xs text-red-500 mt-0.5">{acc.sync_error}</p>
                  ) : (
                    <p className="text-xs text-gray-400 mt-0.5">
                      {acc.last_synced ? `Last synced ${format(new Date(acc.last_synced), 'MMM d, HH:mm')}` : 'Pending first sync (tonight at 06:00 IST)'}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => setRemoveId(acc.id)}
                  className="text-xs text-gray-400 hover:text-red-500 transition-colors"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Add Account Modal ──────────────────────────────────────────────── */}
      <Modal
        open={showAdd}
        onClose={() => setShowAdd(false)}
        title="Connect AWS account"
        footer={
          step === 1 ? (
            <button className="btn-primary" onClick={() => setStep(2)}>
              I've run the Terraform →
            </button>
          ) : (
            <>
              <button className="btn-ghost" onClick={() => setStep(1)}>← Back</button>
              <button className="btn-primary" onClick={handleSubmit} disabled={addAccount.isPending}>
                {addAccount.isPending ? 'Connecting…' : 'Connect account'}
              </button>
            </>
          )
        }
      >
        {step === 1 && (
          <div className="space-y-4">
            <AlertBanner type="info">
              We use read-only access — CloudGuard <strong>cannot</strong> create, modify, or delete anything in your AWS account.
            </AlertBanner>

            <div>
              <SectionTitle>Step 1 — Run this in your AWS account</SectionTitle>
              <p className="text-sm text-gray-500 mb-3">
                Copy the Terraform below into a file and run <code className="bg-gray-100 px-1 rounded text-xs">terraform apply</code>.
                This creates a read-only IAM role that CloudGuard can use.
              </p>

              {extIdData ? (
                <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
                  <pre className="text-xs text-green-400 font-mono whitespace-pre">{`# Save as cloudguard-role.tf and run: terraform apply

variable "external_id" {
  default = "${extIdData.external_id}"
}

resource "aws_iam_role" "cloudguard_readonly" {
  name = "CloudGuardReadOnly"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { AWS = "arn:aws:iam::${extIdData.your_account_id}:role/cloudguard-prod-lambda-role" }
      Condition = { StringEquals = { "sts:ExternalId" = var.external_id } }
    }]
  })
}

resource "aws_iam_role_policy" "cloudguard" {
  role   = aws_iam_role.cloudguard_readonly.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ce:GetCostAndUsage","ce:GetCostForecast","cloudwatch:GetMetricData","cloudwatch:GetMetricStatistics","ec2:DescribeInstances","ec2:DescribeVolumes","ec2:DescribeAddresses","rds:DescribeDBInstances","tag:GetResources"]
      Resource = "*"
    }]
  })
}

output "role_arn" { value = aws_iam_role.cloudguard_readonly.arn }`}</pre>
                </div>
              ) : (
                <div className="h-40 bg-gray-100 rounded-lg animate-pulse" />
              )}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <SectionTitle>Step 2 — Enter the Role ARN</SectionTitle>
            <p className="text-sm text-gray-500">
              After running Terraform, copy the <code className="bg-gray-100 px-1 rounded text-xs">role_arn</code> output and paste it below.
            </p>

            {error && <AlertBanner type="error">{error}</AlertBanner>}

            <div>
              <label className="label">Account nickname</label>
              <input
                className="input"
                placeholder="e.g. Production, Staging, Marketing"
                value={form.account_name}
                onChange={(e) => setForm((f) => ({ ...f, account_name: e.target.value }))}
              />
            </div>
            <div>
              <label className="label">AWS account ID (12 digits)</label>
              <input
                className="input font-mono"
                placeholder="123456789012"
                maxLength={12}
                value={form.account_id}
                onChange={(e) => setForm((f) => ({ ...f, account_id: e.target.value.replace(/\D/g, '') }))}
              />
            </div>
            <div>
              <label className="label">Role ARN (from Terraform output)</label>
              <input
                className="input font-mono text-xs"
                placeholder="arn:aws:iam::123456789012:role/CloudGuardReadOnly"
                value={form.role_arn}
                onChange={(e) => setForm((f) => ({ ...f, role_arn: e.target.value.trim() }))}
              />
            </div>
          </div>
        )}
      </Modal>

      {/* Remove confirm modal */}
      <Modal
        open={!!removeId}
        onClose={() => setRemoveId(null)}
        title="Remove AWS account?"
        footer={
          <>
            <button className="btn-ghost" onClick={() => setRemoveId(null)}>Cancel</button>
            <button className="btn-primary bg-red-500 hover:bg-red-600" onClick={handleRemove} disabled={removeAccount.isPending}>
              {removeAccount.isPending ? 'Removing…' : 'Remove'}
            </button>
          </>
        }
      >
        <p className="text-sm text-gray-600">
          This stops CloudGuard from collecting data for this account. Your cost history is kept.
          You can also delete the IAM role from your AWS account at any time.
        </p>
      </Modal>
    </div>
  )
}
