# import requests
# from ...secret import secret
# from ..scrap.databaseComm2 import DatabaseComm
# headers = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
#     "Accept": "application/json, text/plain, */*",
#     "Accept-Language": "en-NZ,en;q=0.9",
#     "Referer": "https://www.woolworths.co.nz/",
#     "x-requested-with": "OnlineShopping.WebApp",
#     "x-ui-ver": "7.72.37"   
# }
# connection = DatabaseComm(hostName="localhost", 
#                           dbName="supermarketdb", 
#                           username="postgres", 
#                           password= secret.psqlPassword())

# connection.connectionFun()

# def getCatagoriesMain():
#     r = requests.get(url="https://www.woolworths.co.nz/api/v1/shell", headers=headers)
#     data = r.json()

#     x = data.get("mainNavs")[1].get("navigationItems")[0].get("items")
#     for el in x:
#         did = el.get("id")
#         label = el.get("label")
#         connection.insertDepartmentIntoDepartmentTable(deptId=did, deptName=label)
#         print(did, label)
#     connection.commitAndCloseConnection()


# def main():
#     getCatagoriesMain()

# main()