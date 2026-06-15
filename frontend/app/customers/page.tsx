import { CustomerTable } from '@/components/customers/CustomerTable'
import { AppShell } from '@/components/layout/AppShell'

export default function CustomersPage() {
  return (
    <AppShell>
      <CustomerTable />
    </AppShell>
  )
}
