// ========== HR Automation Logic Apps ========== //
// Deploys 5 Logic Apps for email-driven and scheduled HR automation.
// These Logic Apps integrate with the multi-agent backend API and
// the Approval MCP Server Azure Function.
// Includes the Office 365 API connection for email triggers.

@description('Required. Solution suffix used for resource naming.')
param solutionSuffix string

@description('Optional. Location for all resources.')
param location string = resourceGroup().location

@description('Optional. Tags to apply to all resources.')
param tags object = {}

@description('Required. Backend API base URL (e.g. https://ca-backend.xxx.azurecontainerapps.io).')
param backendApiUrl string

@description('Required. Approval MCP Function App base URL.')
param approvalMcpUrl string

@description('Required. HR team ID for task submission.')
param hrTeamId string = '00000000-0000-0000-0000-000000000001'

@description('Optional. Email address for HR automation triggers and approvals.')
param hrMailbox string = 'justinjoy@microsoft.com'

@description('Optional. Email address for approval responses.')
param approvalsMailbox string = 'justinjoy@microsoft.com'

@description('Required. User principal ID used for backend API authentication.')
param userPrincipalId string = 'justinjoy@microsoft.com'

@description('Required. Azure Document Intelligence endpoint for OCR.')
param docIntelligenceEndpoint string = 'https://ai-justinjoy-4099.cognitiveservices.azure.com'

@description('Required. Azure Document Intelligence API key.')
@secure()
param docIntelligenceKey string

@description('Required. Monitor dashboard base URL for approval links.')
param monitorUrl string = 'https://ca-monitor.delightfulsmoke-0952149e.swedencentral.azurecontainerapps.io'

// ========== Office 365 API Connection ========== //
resource office365Connection 'Microsoft.Web/connections@2016-06-01' = {
  name: 'office365-${solutionSuffix}'
  location: location
  tags: tags
  properties: {
    displayName: 'Office 365 - HR Automation (${hrMailbox})'
    api: {
      id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'office365')
    }
  }
}

// Connection ID reference used by all Logic Apps
var o365ConnectionId = office365Connection.id
var o365ConnectionApiId = subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'office365')

// ========== Logic App 1: New Hire Trigger ========== //
resource newHireTrigger 'Microsoft.Logic/workflows@2019-05-01' = {
  name: 'logic-newhire-${solutionSuffix}'
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    state: 'Enabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      triggers: {
        'When_a_new_email_arrives': {
          type: 'ApiConnection'
          inputs: {
            host: {
              connection: {
                name: '@parameters(\'$connections\')[\'office365\'][\'connectionId\']'
              }
            }
            method: 'get'
            path: '/v2/Mail/OnNewEmail'
            queries: {
              folderPath: 'Inbox'
              to: hrMailbox
              subjectFilter: '[NEW HIRE]'
              importance: 'Any'
              includeAttachments: true
            }
          }
          recurrence: {
            frequency: 'Minute'
            interval: 5
          }
        }
      }
      actions: {
        'Check_Has_Attachments': {
          type: 'If'
          expression: {
            and: [
              {
                equals: [
                  '@triggerBody()?[\'value\'][0]?[\'hasAttachments\']'
                  true
                ]
              }
              {
                not: {
                  equals: [
                    '@triggerBody()?[\'value\'][0]?[\'attachments\']'
                    ''
                  ]
                }
              }
            ]
          }
          runAfter: {}
          actions: {
            'OCR_Document': {
              type: 'Http'
              inputs: {
                method: 'POST'
                uri: '${docIntelligenceEndpoint}/documentintelligence/documentModels/prebuilt-layout:analyze?api-version=2024-11-30&outputContentFormat=markdown'
                headers: {
                  'Content-Type': 'application/json'
                }
                body: {
                  base64Source: '@{triggerBody()?[\'value\'][0]?[\'attachments\'][0]?[\'contentBytes\']}'
                }
                authentication: {
                  type: 'ManagedServiceIdentity'
                  audience: 'https://cognitiveservices.azure.com'
                }
              }
              runAfter: {}
            }
            'Wait_For_OCR': {
              type: 'Http'
              inputs: {
                method: 'GET'
                uri: '@{outputs(\'OCR_Document\')[\'headers\'][\'Operation-Location\']}'
                authentication: {
                  type: 'ManagedServiceIdentity'
                  audience: 'https://cognitiveservices.azure.com'
                }
              }
              runAfter: {
                'OCR_Document': ['Succeeded']
              }
            }
            'Wait_10s': {
              type: 'Wait'
              inputs: {
                interval: {
                  count: 10
                  unit: 'Second'
                }
              }
              runAfter: {
                'Wait_For_OCR': ['Succeeded']
              }
            }
            'Get_OCR_Result': {
              type: 'Http'
              inputs: {
                method: 'GET'
                uri: '@{outputs(\'OCR_Document\')[\'headers\'][\'Operation-Location\']}'
                authentication: {
                  type: 'ManagedServiceIdentity'
                  audience: 'https://cognitiveservices.azure.com'
                }
              }
              runAfter: {
                'Wait_10s': ['Succeeded']
              }
            }
            'Set_OCR_Text': {
              type: 'Compose'
              inputs: '@{body(\'Get_OCR_Result\')?[\'analyzeResult\']?[\'content\']}'
              runAfter: {
                'Get_OCR_Result': ['Succeeded']
              }
            }
          }
          else: {
            actions: {
              'Set_No_Attachment_Text': {
                type: 'Compose'
                inputs: 'No CV/document attached.'
                runAfter: {}
              }
            }
          }
        }
        'Select_HR_Team': {
          type: 'Http'
          inputs: {
            method: 'POST'
            uri: '${backendApiUrl}/api/v4/select_team'
            headers: {
              'Content-Type': 'application/json'
              'x-ms-client-principal-id': userPrincipalId
            }
            body: {
              team_id: hrTeamId
            }
          }
          runAfter: {
            'Check_Has_Attachments': ['Succeeded']
          }
        }
        'Initialize_Team': {
          type: 'Http'
          inputs: {
            method: 'GET'
            uri: '${backendApiUrl}/api/v4/init_team'
            headers: {
              'x-ms-client-principal-id': userPrincipalId
            }
          }
          runAfter: {
            'Select_HR_Team': ['Succeeded']
          }
        }
        'Submit_Onboarding_Task': {
          type: 'Http'
          inputs: {
            method: 'POST'
            uri: '${backendApiUrl}/api/v4/process_request'
            headers: {
              'Content-Type': 'application/json'
              'x-ms-client-principal-id': userPrincipalId
            }
            body: {
              session_id: '@{guid()}'
              description: 'Onboard new employee from email. Subject: @{triggerBody()?[\'value\'][0]?[\'subject\']}. Email body: @{triggerBody()?[\'value\'][0]?[\'bodyPreview\']}. Attached CV/Document (OCR): @{coalesce(outputs(\'Set_OCR_Text\'), outputs(\'Set_No_Attachment_Text\'))}'
            }
          }
          runAfter: {
            'Initialize_Team': ['Succeeded']
          }
        }
        'Send_Approval_Email': {
          type: 'ApiConnection'
          inputs: {
            host: {
              connection: {
                name: '@parameters(\'$connections\')[\'office365\'][\'connectionId\']'
              }
            }
            method: 'post'
            path: '/v2/Mail'
            body: {
              To: hrMailbox
              Subject: '[ACTION REQUIRED] Approve Onboarding Plan - @{triggerBody()?[\'value\'][0]?[\'subject\']}'
              Body: '<h2>New Onboarding Plan Requires Approval</h2><p><strong>Subject:</strong> @{triggerBody()?[\'value\'][0]?[\'subject\']}</p><p><strong>Plan ID:</strong> @{body(\'Submit_Onboarding_Task\')?[\'plan_id\']}</p><p><strong>Email Body:</strong><br/>@{triggerBody()?[\'value\'][0]?[\'bodyPreview\']}</p><hr/><p>Click below to approve or reject:</p><p><a href="${monitorUrl}/api/email-approve/@{body(\'Submit_Onboarding_Task\')?[\'plan_id\']}?decision=approved" style="background:#238636;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;font-weight:bold;margin-right:12px;">✅ APPROVE</a>&nbsp;&nbsp;<a href="${monitorUrl}/api/email-approve/@{body(\'Submit_Onboarding_Task\')?[\'plan_id\']}?decision=rejected" style="background:#da3633;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;font-weight:bold;">❌ REJECT</a></p><hr/><p style="color:gray;font-size:12px;">Or open the <a href="${monitorUrl}">Monitor Dashboard</a> to review the full plan.</p>'
              IsHtml: true
            }
          }
          runAfter: {
            'Submit_Onboarding_Task': ['Succeeded']
          }
        }
      }
      parameters: {
        '$connections': {
          type: 'Object'
          defaultValue: {}
        }
      }
    }
    parameters: {
      '$connections': {
        value: {
          office365: {
            connectionId: o365ConnectionId
            connectionName: office365Connection.name
            id: o365ConnectionApiId
          }
        }
      }
    }
  }
}

// ========== Logic App 2: Separation Trigger ========== //
resource separationTrigger 'Microsoft.Logic/workflows@2019-05-01' = {
  name: 'logic-separation-${solutionSuffix}'
  location: location
  tags: tags
  properties: {
    state: 'Enabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      triggers: {
        'When_a_separation_email_arrives': {
          type: 'ApiConnection'
          inputs: {
            host: {
              connection: {
                name: '@parameters(\'$connections\')[\'office365\'][\'connectionId\']'
              }
            }
            method: 'get'
            path: '/v2/Mail/OnNewEmail'
            queries: {
              folderPath: 'Inbox'
              to: hrMailbox
              subjectFilter: '[SEPARATION]'
              importance: 'Any'
            }
          }
          recurrence: {
            frequency: 'Minute'
            interval: 5
          }
        }
      }
      actions: {
        'Select_HR_Team': {
          type: 'Http'
          inputs: {
            method: 'POST'
            uri: '${backendApiUrl}/api/v4/select_team'
            headers: {
              'Content-Type': 'application/json'
              'x-ms-client-principal-id': userPrincipalId
            }
            body: {
              team_id: hrTeamId
            }
          }
          runAfter: {}
        }
        'Initialize_Team': {
          type: 'Http'
          inputs: {
            method: 'GET'
            uri: '${backendApiUrl}/api/v4/init_team'
            headers: {
              'x-ms-client-principal-id': userPrincipalId
            }
          }
          runAfter: {
            'Select_HR_Team': ['Succeeded']
          }
        }
        'Submit_Offboarding_Task': {
          type: 'Http'
          inputs: {
            method: 'POST'
            uri: '${backendApiUrl}/api/v4/process_request'
            headers: {
              'Content-Type': 'application/json'
              'x-ms-client-principal-id': userPrincipalId
            }
            body: {
              session_id: '@{guid()}'
              description: 'Offboard employee from separation email. Subject: @{triggerBody()?[\'value\'][0]?[\'subject\']}. Email body: @{triggerBody()?[\'value\'][0]?[\'bodyPreview\']}'
            }
          }
          runAfter: {
            'Initialize_Team': ['Succeeded']
          }
        }
      }
      parameters: {
        '$connections': {
          type: 'Object'
          defaultValue: {}
        }
      }
    }
    parameters: {
      '$connections': {
        value: {
          office365: {
            connectionId: o365ConnectionId
            connectionName: office365Connection.name
            id: o365ConnectionApiId
          }
        }
      }
    }
  }
}

// ========== Logic App 3: Approval Response Handler ========== //
resource approvalResponseHandler 'Microsoft.Logic/workflows@2019-05-01' = {
  name: 'logic-approval-${solutionSuffix}'
  location: location
  tags: tags
  properties: {
    state: 'Enabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      triggers: {
        'When_approval_response_arrives': {
          type: 'ApiConnection'
          inputs: {
            host: {
              connection: {
                name: '@parameters(\'$connections\')[\'office365\'][\'connectionId\']'
              }
            }
            method: 'get'
            path: '/v2/Mail/OnNewEmail'
            queries: {
              folderPath: 'Inbox'
              to: approvalsMailbox
              subjectFilter: '[APPROVAL:'
              importance: 'Any'
            }
          }
          recurrence: {
            frequency: 'Minute'
            interval: 2
          }
        }
      }
      actions: {
        'Extract_Approval_ID': {
          type: 'Compose'
          inputs: '@split(split(triggerBody()?[\'value\'][0]?[\'subject\'], \'[APPROVAL:\')[1], \']\')[0]'
          runAfter: {}
        }
        'Determine_Decision': {
          type: 'Compose'
          inputs: '@if(contains(toLower(triggerBody()?[\'value\'][0]?[\'bodyPreview\']), \'approved\'), \'approved\', \'rejected\')'
          runAfter: {}
        }
        'Send_Decision_To_Approval_MCP': {
          type: 'Http'
          inputs: {
            method: 'POST'
            uri: '${approvalMcpUrl}/api/approval/@{outputs(\'Extract_Approval_ID\')}/respond'
            headers: {
              'Content-Type': 'application/json'
            }
            body: {
              decision: '@outputs(\'Determine_Decision\')'
              approver: '@triggerBody()?[\'value\'][0]?[\'from\']'
              comments: '@triggerBody()?[\'value\'][0]?[\'bodyPreview\']'
            }
          }
          runAfter: {
            'Extract_Approval_ID': ['Succeeded']
            'Determine_Decision': ['Succeeded']
          }
        }
      }
      parameters: {
        '$connections': {
          type: 'Object'
          defaultValue: {}
        }
      }
    }
    parameters: {
      '$connections': {
        value: {
          office365: {
            connectionId: o365ConnectionId
            connectionName: office365Connection.name
            id: o365ConnectionApiId
          }
        }
      }
    }
  }
}

// ========== Logic App 4: Calendar-Driven Reminders ========== //
resource calendarReminders 'Microsoft.Logic/workflows@2019-05-01' = {
  name: 'logic-reminders-${solutionSuffix}'
  location: location
  tags: tags
  properties: {
    state: 'Enabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      triggers: {
        'Daily_8AM_Recurrence': {
          type: 'Recurrence'
          recurrence: {
            frequency: 'Day'
            interval: 1
            schedule: {
              hours: [8]
              minutes: [0]
            }
            timeZone: 'UTC'
          }
        }
      }
      actions: {
        'Select_HR_Team': {
          type: 'Http'
          inputs: {
            method: 'POST'
            uri: '${backendApiUrl}/api/v4/select_team'
            headers: {
              'Content-Type': 'application/json'
              'x-ms-client-principal-id': userPrincipalId
            }
            body: {
              team_id: hrTeamId
            }
          }
          runAfter: {}
        }
        'Submit_Reminder_Task': {
          type: 'Http'
          inputs: {
            method: 'POST'
            uri: '${backendApiUrl}/api/v4/process_request'
            headers: {
              'Content-Type': 'application/json'
              'x-ms-client-principal-id': userPrincipalId
            }
            body: {
              session_id: '@{guid()}'
              description: 'Check for employees starting tomorrow. For each one: send Day 1 reminder email to the employee and their manager, verify their badge is provisioned via Facilities MCP, and confirm their workspace is ready.'
            }
          }
          runAfter: {
            'Select_HR_Team': ['Succeeded']
          }
        }
      }
    }
  }
}

// ========== Logic App 5: Knowledge Transfer Nudge ========== //
resource knowledgeTransferNudge 'Microsoft.Logic/workflows@2019-05-01' = {
  name: 'logic-kt-nudge-${solutionSuffix}'
  location: location
  tags: tags
  properties: {
    state: 'Enabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      triggers: {
        'Weekly_Monday_Recurrence': {
          type: 'Recurrence'
          recurrence: {
            frequency: 'Week'
            interval: 1
            schedule: {
              weekDays: ['Monday']
              hours: [9]
              minutes: [0]
            }
            timeZone: 'UTC'
          }
        }
      }
      actions: {
        'Select_HR_Team': {
          type: 'Http'
          inputs: {
            method: 'POST'
            uri: '${backendApiUrl}/api/v4/select_team'
            headers: {
              'Content-Type': 'application/json'
              'x-ms-client-principal-id': userPrincipalId
            }
            body: {
              team_id: hrTeamId
            }
          }
          runAfter: {}
        }
        'Submit_KT_Nudge_Task': {
          type: 'Http'
          inputs: {
            method: 'POST'
            uri: '${backendApiUrl}/api/v4/process_request'
            headers: {
              'Content-Type': 'application/json'
              'x-ms-client-principal-id': userPrincipalId
            }
            body: {
              session_id: '@{guid()}'
              description: 'Check knowledge transfer progress for all employees currently in their notice period. If completion is below 80%, send a nudge email to the employee and their manager. If the notice period ends in less than 3 days and completion is below 50%, escalate to the HR director.'
            }
          }
          runAfter: {
            'Select_HR_Team': ['Succeeded']
          }
        }
      }
    }
  }
}

// ========== Outputs ========== //

@description('Resource ID of the Office 365 API Connection. Authorize this in Azure Portal > API Connections.')
output office365ConnectionResourceId string = office365Connection.id

@description('Resource ID of the New Hire Trigger Logic App.')
output newHireTriggerResourceId string = newHireTrigger.id

@description('Resource ID of the Separation Trigger Logic App.')
output separationTriggerResourceId string = separationTrigger.id

@description('Resource ID of the Approval Response Handler Logic App.')
output approvalResponseResourceId string = approvalResponseHandler.id

@description('Resource ID of the Calendar Reminders Logic App.')
output calendarRemindersResourceId string = calendarReminders.id

@description('Resource ID of the Knowledge Transfer Nudge Logic App.')
output knowledgeTransferNudgeResourceId string = knowledgeTransferNudge.id
