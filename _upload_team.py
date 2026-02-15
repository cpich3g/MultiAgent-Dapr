import json, os
from azure.cosmos import CosmosClient

endpoint = os.environ['COSMOS_ENDPOINT']
key = os.environ['COSMOS_KEY']

client = CosmosClient(endpoint, key)
db = client.get_database_client('macae')
container = db.get_container_client('memory')

with open('data/agent_teams/hr.json') as f:
    team = json.load(f)

team['id'] = '00000000-0000-0000-0000-000000000001'
team['team_id'] = '00000000-0000-0000-0000-000000000001'
team['data_type'] = 'team_config'
team['session_id'] = 'global'

container.upsert_item(team)
print('Uploaded ' + str(len(team['agents'])) + ' agents with MCP disabled')
