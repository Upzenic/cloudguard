// src/components/layout/Sidebar.jsx
import { NavLink } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'

const NAV = [
  { to: '/dashboard',  icon: '▦',  label: 'Dashboard'       },
  { to: '/costs',      icon: '₹',  label: 'Cost History'    },
  { to: '/resources',  icon: '⚡', label: 'Idle Resources'  },
  { to: '/accounts',   icon: '☁',  label: 'AWS Accounts'    },
  { to: '/alerts',     icon: '🔔', label: 'Alert Settings'  },
  { to: '/billing',    icon: '💳', label: 'Billing'         },
]

export default function Sidebar() {
  const { user, logout } = useAuthStore()

  return (
    <aside className="w-56 bg-white border-r border-gray-200 flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-brand-500 flex items-center justify-center text-white text-xs font-bold">
            CG
          </div>
          <span className="font-semibold text-sm text-gray-900">CloudGuard</span>
        </div>
        {user?.company_name && (
          <p className="text-xs text-gray-400 mt-1 truncate pl-9">{user.company_name}</p>
        )}
      </div>

      {/* Nav links */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-brand-50 text-brand-600 font-medium'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`
            }
          >
            <span className="text-base w-5 text-center">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User footer */}
      <div className="px-3 py-3 border-t border-gray-100">
        <div className="flex items-center gap-2 px-3 py-2">
          <div className="w-7 h-7 rounded-full bg-brand-100 text-brand-600 flex items-center justify-center text-xs font-semibold flex-shrink-0">
            {user?.email?.[0]?.toUpperCase() ?? 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-gray-900 truncate">{user?.email ?? 'User'}</p>
            <p className="text-xs text-gray-400 capitalize">{user?.plan ?? 'starter'} plan</p>
          </div>
        </div>
        <button
          onClick={logout}
          className="w-full text-left text-xs text-gray-400 hover:text-gray-600 px-3 py-1.5 rounded transition-colors"
        >
          Sign out
        </button>
      </div>
    </aside>
  )
}
