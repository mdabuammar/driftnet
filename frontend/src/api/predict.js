const API_BASE = 'http://localhost:8000'

// Maps dot-notation internal keys to underscore-notation form field names
const FIELD_MAP = {
  'demographic.gender':                  'demographic_gender',
  'demographic.vital_status':            'demographic_vital_status',
  'samples.sample_type':                 'samples_sample_type',
  'cases.disease_type':                  'cases_disease_type',
  'samples.tissue_type':                 'samples_tissue_type',
  'diagnoses.primary_diagnosis':         'diagnoses_primary_diagnosis',
  'diagnoses.tissue_or_organ_of_origin': 'diagnoses_tissue_or_organ_of_origin',
  'diagnoses.morphology':                'diagnoses_morphology',
  'diagnoses.age_at_diagnosis':          'diagnoses_age_at_diagnosis',
  'diagnoses.prior_treatment':           'diagnoses_prior_treatment',
  'diagnoses.prior_malignancy':          'diagnoses_prior_malignancy',
  'demographic.race':                    'demographic_race',
  'demographic.ethnicity':               'demographic_ethnicity',
}

/**
 * Submits a methylation file + clinical values to the DriftNet /predict endpoint.
 * @param {File} file - The uploaded methylation .txt file
 * @param {Object} clinicalValues - Keyed by dot-notation field names
 * @returns {Promise<Object>} - The parsed JSON prediction response
 */
export async function predictStage(file, clinicalValues) {
  const formData = new FormData()
  formData.append('methylation_file', file)

  for (const [dotKey, formKey] of Object.entries(FIELD_MAP)) {
    formData.append(formKey, clinicalValues[dotKey])
  }

  const response = await fetch(`${API_BASE}/predict`, {
    method: 'POST',
    body: formData,
  })

  // For non-2xx responses, try to parse a meaningful error message
  if (!response.ok) {
    let detail = `Server returned ${response.status}`
    try {
      const err = await response.json()
      detail = err.detail || err.error_message || detail
    } catch (_) {
      // ignore parse failure
    }
    const error = new Error(detail)
    error.status = response.status
    throw error
  }

  return response.json()
}

/**
 * Health check — confirms the backend is reachable and models are loaded.
 */
export async function checkHealth() {
  const response = await fetch(`${API_BASE}/health`)
  if (!response.ok) throw new Error('Backend not reachable')
  return response.json()
}
