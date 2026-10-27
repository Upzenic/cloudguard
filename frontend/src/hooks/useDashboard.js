// src/hooks/useDashboard.js
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getDashboard,
  addAWSAccount,
  removeAWSAccount,
  updateAlertConfig,
  dismissIdleResource,
  generateExternalId,
} from '../services/api'

export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn:  getDashboard,
    refetchInterval: 5 * 60 * 1000, // Refresh every 5 minutes
    staleTime:       2 * 60 * 1000,
  })
}

export function useAddAWSAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: addAWSAccount,
    onSuccess:  () => qc.invalidateQueries({ queryKey: ['dashboard'] }),
  })
}

export function useRemoveAWSAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: removeAWSAccount,
    onSuccess:  () => qc.invalidateQueries({ queryKey: ['dashboard'] }),
  })
}

export function useUpdateAlertConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateAlertConfig,
    onSuccess:  () => qc.invalidateQueries({ queryKey: ['dashboard'] }),
  })
}

export function useDismissResource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: dismissIdleResource,
    onSuccess:  () => qc.invalidateQueries({ queryKey: ['dashboard'] }),
  })
}

export function useGenerateExternalId() {
  return useMutation({ mutationFn: generateExternalId })
}
