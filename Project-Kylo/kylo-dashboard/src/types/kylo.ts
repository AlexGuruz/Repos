export interface InstanceRow {
  instance_id: string;
  company_key: string;
  active_years: string;
  last_tick_at: string;
  last_post_at: string;
  last_post_ok: string;
  cells_written: number;
  rows_marked_true: number;
  skipped_no_rule: number;
  last_error: string;
}

export interface DashboardData {
  schema_version: number;
  updated_at: string;
  instances: InstanceRow[];
}

export interface HubStatus {
  updated_at: string;
  instances: Record<string, {
    pid: number | null;
    enabled: boolean;
    state: string;
    started_at: string | null;
    restarts: number;
    last_exit: number | null;
    health_path: string;
    log_path: string;
    years: string;
    last_error?: string;
  }>;
}

export interface Heartbeat {
  instance_id: string;
  company_key: string;
  active_years: number[] | null;
  last_tick_at: string | null;
  last_tick_duration_ms: number | null;
  last_post_ok: boolean | null;
  last_error: string | null;
  change_detected: boolean;
  posting_attempted: boolean;
  posting_skipped_reason: string | null;
}

