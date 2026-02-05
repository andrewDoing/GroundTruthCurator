metadata name = 'Ground Truth Curator Infrastructure'
metadata description = 'Deploys shared infrastructure for Ground Truth Curator (Cosmos DB + Container Apps environment).'

targetScope = 'resourceGroup'

/* Types */
@description('Resource tags applied to resources.')
type ResourceTags = {
  *: string
}

@description('Cosmos DB consistency level.')
type CosmosConsistencyLevel =
  | 'Eventual'
  | 'ConsistentPrefix'
  | 'Session'
  | 'BoundedStaleness'
  | 'Strong'

/* Common parameters */
@description('Azure region for resources.')
param location string

@description('Resource name prefix.')
param resourcePrefix string

@description('Deployment environment name (dev, test, prod).')
param environment string

@description('Resource tags applied to all resources.')
param tags ResourceTags = {}

/* Cosmos parameters */
@description('Cosmos DB account name. (If null, a unique name is generated.)')
param cosmosAccountName string?

@description('Cosmos DB SQL database name.')
param cosmosDatabaseName string

@description('Enable serverless capacity mode for Cosmos DB.')
param cosmosShouldEnableServerless bool = false

@description('Cosmos DB consistency level.')
param cosmosConsistencyLevel CosmosConsistencyLevel = 'Session'

/* Identity parameters */
@description('User-assigned managed identity name. (If null, a default name is generated.)')
param managedIdentityName string?

@description('Should assign a Cosmos DB data role to the managed identity.')
param cosmosShouldAssignDataRole bool = true

@description('Cosmos DB data role definition name (GUID).')
param cosmosDataRoleDefinitionName string = '00000000-0000-0000-0000-000000000002'

@description('Cosmos DB data role scope for the assignment. (If null, defaults to the SQL database scope.)')
param cosmosDataRoleScope string?

/* Log Analytics parameters */
@description('Log Analytics workspace name. (If null, a default name is generated.)')
param logAnalyticsWorkspaceName string?

@description('Log Analytics retention in days.')
param logAnalyticsRetentionInDays int = 30

/* Container Apps parameters */
@description('Container Apps managed environment name. (If null, a default name is generated.)')
param containerAppsEnvironmentName string?

/* Variables */
var normalizedPrefix = toLower(replace(resourcePrefix, '-', ''))
var resolvedCosmosAccountName = cosmosAccountName ?? take('${normalizedPrefix}${environment}${uniqueString(resourceGroup().id)}', 44)
var resolvedLogAnalyticsName = logAnalyticsWorkspaceName ?? '${resourcePrefix}-${environment}-law'
var resolvedContainerAppsEnvName = containerAppsEnvironmentName ?? '${resourcePrefix}-${environment}-cae'
var resolvedManagedIdentityName = managedIdentityName ?? '${resourcePrefix}-${environment}-mi'
var cosmosDataRoleDefinitionId = resourceId(
  'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions',
  resolvedCosmosAccountName,
  cosmosDataRoleDefinitionName
)
var resolvedCosmosDataRoleScope = cosmosDataRoleScope ?? '${cosmosAccount.id}/dbs/${cosmosDatabaseName}'

/* Resources */
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: resolvedLogAnalyticsName
  location: location
  tags: tags
  properties: {
    retentionInDays: logAnalyticsRetentionInDays
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: resolvedManagedIdentityName
  location: location
  tags: tags
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: resolvedContainerAppsEnvName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: resolvedCosmosAccountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: cosmosConsistencyLevel
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    enableAutomaticFailover: false
    capabilities: cosmosShouldEnableServerless ? [
      {
        name: 'EnableServerless'
      }
    ] : []
  }
}

resource cosmosSqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  name: cosmosDatabaseName
  parent: cosmosAccount
  properties: {
    resource: {
      id: cosmosDatabaseName
    }
    options: {}
  }
}

resource cosmosDataRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-11-15' = if (cosmosShouldAssignDataRole) {
  name: guid(cosmosAccount.id, managedIdentity.id, resolvedCosmosDataRoleScope)
  parent: cosmosAccount
  properties: {
    roleDefinitionId: cosmosDataRoleDefinitionId
    principalId: managedIdentity.properties.principalId
    scope: resolvedCosmosDataRoleScope
  }
}

/* Outputs */
@description('Cosmos DB account name.')
output cosmosAccountName string = cosmosAccount.name

@description('Cosmos DB account endpoint.')
output cosmosAccountEndpoint string = cosmosAccount.properties.documentEndpoint

@description('Cosmos DB SQL database name.')
output cosmosDatabaseName string = cosmosSqlDatabase.name

@description('Log Analytics workspace resource ID.')
output logAnalyticsWorkspaceResourceId string = logAnalyticsWorkspace.id

@description('Log Analytics workspace customer ID.')
output logAnalyticsWorkspaceCustomerId string = logAnalyticsWorkspace.properties.customerId

@description('Container Apps managed environment name.')
output containerAppsEnvironmentName string = containerAppsEnvironment.name

@description('Container Apps managed environment resource ID.')
output containerAppsEnvironmentId string = containerAppsEnvironment.id

@description('User-assigned managed identity resource ID.')
output managedIdentityId string = managedIdentity.id

@description('User-assigned managed identity client ID.')
output managedIdentityClientId string = managedIdentity.properties.clientId

@description('User-assigned managed identity principal ID.')
output managedIdentityPrincipalId string = managedIdentity.properties.principalId

@description('Cosmos data role assignment resource ID, if created.')
output cosmosDataRoleAssignmentId string? = cosmosShouldAssignDataRole ? cosmosDataRoleAssignment.id : null
