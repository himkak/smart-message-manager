// Phase 0 placeholder. Azure resources are intentionally not deployed automatically.
targetScope = 'resourceGroup'

@description('Reserved for the Smart Messages Manager resource definitions in a later phase.')
param location string = resourceGroup().location

output plannedResources array = [
  'Azure AI Search'
  'Azure OpenAI / Microsoft Foundry'
  'Storage account'
  'Container Apps environment'
  'Application Insights'
  'Key Vault'
]

