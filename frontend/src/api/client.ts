import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Jobs API
export const jobsApi = {
  list: (status?: string) =>
    api.get('/jobs', { params: { status } }).then(res => res.data),

  get: (id: number) =>
    api.get(`/jobs/${id}`).then(res => res.data),

  create: (url: string) =>
    api.post('/jobs', { url }).then(res => res.data),

  delete: (id: number) =>
    api.delete(`/jobs/${id}`).then(res => res.data),

  retry: (id: number) =>
    api.post(`/jobs/${id}/retry`).then(res => res.data),

  submitCompany: (
    id: number,
    companyName: string,
    siteType: 'company' | 'platform' = 'company',
    platformName?: string
  ) =>
    api.post(`/jobs/${id}/company`, {
      company_name: companyName,
      site_type: siteType,
      platform_name: platformName,
    }).then(res => res.data),

  triggerProcess: (id: number) =>
    api.post(`/jobs/${id}/process`).then(res => res.data),

  triggerWorkflow: (id: number, templateId?: number) =>
    api.post(`/jobs/${id}/workflow`, { template_id: templateId }).then(res => res.data),

  searchConnections: (id: number) =>
    api.post(`/jobs/${id}/search-connections`).then(res => res.data),

  submitHebrewNames: (id: number, names: { english_name: string; hebrew_name: string }[]) =>
    api.post(`/jobs/${id}/hebrew-names`, { names }).then(res => res.data),

  getPendingHebrewNames: (id: number) =>
    api.get(`/jobs/${id}/pending-hebrew-names`).then(res => res.data),
}

// Templates API
export const templatesApi = {
  list: () =>
    api.get('/templates').then(res => res.data),

  get: (id: number) =>
    api.get(`/templates/${id}`).then(res => res.data),

  create: (data: {
    name: string
    content_male: string
    content_female: string
    content_neutral: string
    is_default?: boolean
  }) =>
    api.post('/templates', data).then(res => res.data),

  update: (id: number, data: Partial<{
    name: string
    content_male: string
    content_female: string
    content_neutral: string
    is_default: boolean
  }>) =>
    api.put(`/templates/${id}`, data).then(res => res.data),

  delete: (id: number) =>
    api.delete(`/templates/${id}`).then(res => res.data),

  preview: (id: number, gender: string, name?: string, company?: string) =>
    api.post(`/templates/${id}/preview`, { gender, name, company }).then(res => res.data),
}

// Selectors API
export const selectorsApi = {
  list: () =>
    api.get('/selectors').then(res => res.data),

  create: (data: {
    domain: string
    company_selector: string
    title_selector?: string
    example_url?: string
    example_company?: string
  }) =>
    api.post('/selectors', data).then(res => res.data),

  delete: (id: number) =>
    api.delete(`/selectors/${id}`).then(res => res.data),

  check: (url: string) =>
    api.post('/selectors/check', null, { params: { url } }).then(res => res.data),
}

// Logs API
export const logsApi = {
  list: (params?: { action_type?: string; job_id?: number; skip?: number; limit?: number }) =>
    api.get('/logs', { params }).then(res => res.data),

  stats: () =>
    api.get('/logs/stats').then(res => res.data),

  recent: (limit?: number) =>
    api.get('/logs/recent', { params: { limit } }).then(res => res.data),

  forJob: (jobId: number) =>
    api.get(`/logs/job/${jobId}`).then(res => res.data),
}

// Auth API
export const authApi = {
  status: () =>
    api.get('/auth/status').then(res => res.data),

  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }).then(res => res.data),

  loginWithBrowser: () =>
    api.post('/auth/login-browser').then(res => res.data),

  logout: () =>
    api.post('/auth/logout').then(res => res.data),
}

export default api
