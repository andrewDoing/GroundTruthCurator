from azure.cosmos import CosmosClient, exceptions

# Connect to the emulator
ENDPOINT = "http://localhost:8081"
KEY = "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="  # well-known emulator key

client = CosmosClient(ENDPOINT, credential=KEY)

# Iterate through all databases and delete them
for db_props in client.list_databases():
    db_name = db_props["id"]
    print(f"Deleting database: {db_name}")
    try:
        client.delete_database(db_name)
        print(f"  → Deleted '{db_name}'")
    except exceptions.CosmosHttpResponseError as e:
        print(f"  ! Failed to delete '{db_name}': {e.message}")
