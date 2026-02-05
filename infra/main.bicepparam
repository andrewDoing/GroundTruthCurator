using 'main.bicep'

var prefix = 'gtc'
var env = 'dev'

param resourcePrefix = prefix
param environment = env
param location = 'eastus2'
param cosmosDatabaseName = 'gt-curator'
param cosmosShouldEnableServerless = true
param cosmosShouldAssignDataRole = true
param tags = {
  environment: env
  project: 'ground-truth-curator'
}
