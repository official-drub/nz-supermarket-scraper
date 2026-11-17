# import requests
# from .csvUtility import CsvUtil
# from scraperModule.secret import secret
# from scraperModule.databaseComm2 import DatabaseComm

# get_pickupStores_url = "https://www.woolworths.co.nz/api/v1/addresses/pickup-addresses"
# putreq_pickupStore_url = "https://www.woolworths.co.nz/api/v1/fulfilment/my/pickup-addresses"
# headers = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
#     "Accept": "application/json, text/plain, */*",
#     "Accept-encoding": "gzip, deflate, br, zstd",
#     "Accept-language": "en-NZ,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
#     "Referer": "https://www.woolworths.co.nz/",
#     "x-requested-with": "OnlineShopping.WebApp",
#     "x-ui-ver": "7.74.17"   
# }
# stores = {}
# connection = DatabaseComm(hostName="localhost", 
#                           dbName="supermarketdb", 
#                           username="postgres", 
#                           password= secret.psqlPassword())

# connection.connectionFun()

# # csvStores = CsvUtil("stores.csv")
# # csvStoreIds = CsvUtil("storesIds.csv")




# def addressIdGetter():
#     connection.testingConnection()
#     req = requests.get(headers=headers, url=get_pickupStores_url)
#     data = req.json()
#     # csvStores.writeCSV(option="w", data=["storeId", "storeName", "storeAdr"])
#     # csvStoreIds.writeCSV(option="w", data=["storeId"])


#     for a in data["storeAreas"]:
#         for store in a.get("storeAddresses"):
#             storeId = store.get("id")
#             storeAdr = store.get("address")
#             storeName = store.get("name")
#             if(storeId in stores):
#                 # print(f"duplicate key: {storeId}, {storeName} not added")
#                 continue

#             stores[storeId] = {
#                 "storeName": storeName, 
#                 "storeAdr": storeAdr
#             }

#             connection.insertStoreInStore(storeId=storeId, storeName=storeName, storeAdr=storeAdr)

#             # csvStores.writeCSV(option="a", data=[storeId, storeName, storeAdr])
#             # csvStoreIds.writeCSV(option="a", data=[storeId])
#     connection.commitAndCloseConnection()
#     print("done")
#     return stores



# addressIdGetter()




