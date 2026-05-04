// All valid dropdown options sourced directly from assets/clinical_label_mappings.json

export const CLINICAL_OPTIONS = {
  'demographic.gender': [
    'female',
    'male'
  ],
  'demographic.vital_status': [
    'Alive',
    'Dead'
  ],
  'samples.sample_type': [
    'Primary Tumor',
    'Solid Tissue Normal'
  ],
  'cases.disease_type': [
    'Acinar Cell Neoplasms',
    'Adenomas and Adenocarcinomas',
    'Basal Cell Neoplasms',
    'Complex Epithelial Neoplasms',
    'Cystic, Mucinous and Serous Neoplasms',
    'Ductal and Lobular Neoplasms',
    'Epithelial Neoplasms, NOS',
    'Squamous Cell Neoplasms'
  ],
  'samples.tissue_type': [
    'Normal',
    'Tumor'
  ],
  'diagnoses.primary_diagnosis': [
    'Acinar cell carcinoma',
    'Adenocarcinoma with mixed subtypes',
    'Adenocarcinoma, NOS',
    'Adenoid cystic carcinoma',
    'Basal cell carcinoma, NOS',
    'Basaloid squamous cell carcinoma',
    'Bronchio-alveolar carcinoma, mucinous',
    'Bronchiolo-alveolar adenocarcinoma, NOS',
    'Bronchiolo-alveolar carcinoma, non-mucinous',
    'Carcinoma, NOS',
    'Clear cell adenocarcinoma, NOS',
    'Infiltrating duct and lobular carcinoma',
    'Infiltrating duct carcinoma, NOS',
    'Infiltrating duct mixed with other types of carcinoma',
    'Infiltrating lobular mixed with other types of carcinoma',
    'Intraductal papillary adenocarcinoma with invasion',
    'Invasive micropapillary carcinoma',
    'Lobular carcinoma, NOS',
    'Medullary carcinoma, NOS',
    'Metaplastic carcinoma, NOS',
    'Mucinous adenocarcinoma',
    'Nonencapsulated sclerosing carcinoma',
    'Paget disease and infiltrating duct carcinoma of breast',
    'Papillary adenocarcinoma, NOS',
    'Papillary carcinoma, NOS',
    'Papillary carcinoma, columnar cell',
    'Papillary carcinoma, follicular variant',
    'Papillary squamous cell carcinoma',
    'Pleomorphic carcinoma',
    'Renal cell carcinoma, chromophobe type',
    'Solid carcinoma, NOS',
    'Squamous cell carcinoma, NOS',
    'Squamous cell carcinoma, keratinizing, NOS',
    'Tubular adenocarcinoma'
  ],
  'diagnoses.tissue_or_organ_of_origin': [
    'Breast, NOS',
    'Kidney, NOS',
    'Thyroid gland',
    'Upper lobe, lung'
  ],
  'diagnoses.morphology': [
    '8010/3',
    '8022/3',
    '8050/3',
    '8052/3',
    '8070/3',
    '8071/3',
    '8083/3',
    '8090/3',
    '8140/3',
    '8200/3',
    '8211/3',
    "8230/3",
    "8250/3",
    "8252/3",
    "8253/3",
    "8255/3",
    "8260/3",
    "8310/3",
    "8317/3",
    "8340/3",
    "8344/3",
    "8350/3",
    "8480/3",
    "8500/3",
    "8503/3",
    "8507/3",
    "8510/3",
    "8520/3",
    "8522/3",
    "8523/3",
    "8524/3",
    "8541/3",
    "8550/3",
    "8575/3"
  ],
  'diagnoses.prior_treatment': [
    'No',
    'Yes'
  ],
  'diagnoses.prior_malignancy': [
    'no',
    'yes'
  ],
  'demographic.race': [
    'american indian or alaska native',
    'asian',
    'black or african american',
    'white'
  ],
  'demographic.ethnicity': [
    'hispanic or latino',
    'not hispanic or latino'
  ]
}

// Ordered list of all 13 field keys (must match backend EXPECTED_CLINICAL_COLS order)
export const CLINICAL_FIELD_KEYS = [
  'demographic.gender',
  'demographic.vital_status',
  'samples.sample_type',
  'cases.disease_type',
  'samples.tissue_type',
  'diagnoses.primary_diagnosis',
  'diagnoses.tissue_or_organ_of_origin',
  'diagnoses.morphology',
  'diagnoses.age_at_diagnosis',
  'diagnoses.prior_treatment',
  'diagnoses.prior_malignancy',
  'demographic.race',
  'demographic.ethnicity',
]

// Human-readable labels for each field
export const CLINICAL_LABELS = {
  'demographic.gender':                  'Gender',
  'demographic.vital_status':            'Vital Status',
  'samples.sample_type':                 'Sample Type',
  'cases.disease_type':                  'Disease Type',
  'samples.tissue_type':                 'Tissue Type',
  'diagnoses.primary_diagnosis':         'Primary Diagnosis',
  'diagnoses.tissue_or_organ_of_origin': 'Tissue / Organ of Origin',
  'diagnoses.morphology':                'Morphology Code (ICD-O)',
  'diagnoses.age_at_diagnosis':          'Age at Diagnosis',
  'diagnoses.prior_treatment':           'Prior Treatment',
  'diagnoses.prior_malignancy':          'Prior Malignancy',
  'demographic.race':                    'Race',
  'demographic.ethnicity':               'Ethnicity',
}

// Help text for fields that need clarification
export const CLINICAL_HINTS = {
  'diagnoses.age_at_diagnosis': 'Enter age in days (e.g. 25069 ≈ 68.7 years)',
  'diagnoses.morphology':       'ICD-O morphology code (e.g. 8160/3)',
}

// Logical groupings for the form UI
export const CLINICAL_GROUPS = [
  {
    title:  'Patient Demographics',
    fields: ['demographic.gender', 'demographic.vital_status', 'demographic.race', 'demographic.ethnicity'],
  },
  {
    title:  'Sample Information',
    fields: ['samples.sample_type', 'samples.tissue_type'],
  },
  {
    title:  'Disease Classification',
    fields: ['cases.disease_type'],
  },
  {
    title:  'Diagnosis Details',
    fields: [
      'diagnoses.primary_diagnosis',
      'diagnoses.tissue_or_organ_of_origin',
      'diagnoses.morphology',
      'diagnoses.age_at_diagnosis',
      'diagnoses.prior_treatment',
      'diagnoses.prior_malignancy',
    ],
  },
]

// Initial empty state
export const INITIAL_CLINICAL_VALUES = Object.fromEntries(
  CLINICAL_FIELD_KEYS.map(k => [k, ''])
)
