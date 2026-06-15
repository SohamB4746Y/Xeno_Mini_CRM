export interface Customer {
  id: string
  name: string
  email: string
  phone: string
  city: string
  state: string
  age: number
  gender: string
  tier: 'bronze' | 'silver' | 'gold' | 'platinum'
  preferred_channel: 'whatsapp' | 'sms' | 'email' | 'rcs'
  total_spend: number
  total_orders: number
  last_purchase_at: string | null
  created_at: string
  updated_at?: string
  days_since_purchase: number | null
}

export interface CustomerListResponse {
  items: Customer[]
  total: number
  page: number
  page_size: number
}

export interface DashboardMetrics {
  total_customers: number
  active_segments: number
  campaigns_this_month: number
  total_communications_sent: number
  average_delivery_rate: number
  average_open_rate: number
  best_campaign: { name: string; open_rate: number; click_rate: number } | null
  recent_campaigns: Campaign[]
}

export interface Segment {
  id: string
  name: string
  description: string
  customer_count: number
  ai_generated: boolean
  is_active: boolean
  created_at: string
  filter_rules: Record<string, unknown>
}

export interface SegmentListResponse {
  items: Segment[]
  total: number
}

export interface Campaign {
  id: string
  name: string
  segment_id?: string | null
  channel: string
  status: 'draft' | 'running' | 'completed' | 'paused' | 'failed'
  total_recipients: number
  message_template?: string
  ai_generated_message?: boolean
  ai_generated_segment?: boolean
  launched_at: string | null
  completed_at?: string | null
  created_at: string
  updated_at?: string
  analytics?: CampaignAnalytics | null
}

export interface CampaignListResponse {
  items: Campaign[]
  total: number
}

export interface CampaignAnalytics {
  id?: string
  campaign_id?: string
  total_sent: number
  total_delivered: number
  total_opened: number
  total_clicked: number
  total_converted: number
  total_failed: number
  total_read?: number
  delivery_rate: number
  open_rate: number
  click_rate: number
  conversion_rate: number
  updated_at?: string
}

export interface Communication {
  id: string
  campaign_id: string
  customer_id: string
  channel: string
  personalized_message: string
  status: string
  sent_at: string | null
  delivered_at: string | null
  opened_at: string | null
  clicked_at: string | null
  converted_at: string | null
  failed_at: string | null
  created_at: string
}

export interface CommunicationListResponse {
  items: Communication[]
  total: number
  campaign_id: string
}

export interface OpportunityCard {
  id: string
  priority: 'high' | 'medium' | 'low'
  icon: string
  title: string
  description: string
  suggested_action: string
  estimated_audience: number | null
  quick_prompt: string
  suggested_channel?: string
  suggested_filter_rules?: Record<string, unknown>
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ActionTaken {
  type: string
  campaign_id?: string
  campaign_name?: string
  total_recipients?: number
  segment_id?: string
  segment_name?: string
  customer_count?: number
  [key: string]: unknown
}

export interface ChatResponse {
  response: string
  tools_used: string[]
  actions_taken: ActionTaken[]
  conversation_history: ChatMessage[]
}
