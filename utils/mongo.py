from pymongo import MongoClient

MONGO_URI = "mongodb://carlonana0213_db_user:LikhaNU2026@ac-yah2vuq-shard-00-00.jucnt4q.mongodb.net:27017,ac-yah2vuq-shard-00-01.jucnt4q.mongodb.net:27017,ac-yah2vuq-shard-00-02.jucnt4q.mongodb.net:27017/?ssl=true&replicaSet=atlas-10fvq0-shard-0&authSource=admin&appName=Cluster0"

client = MongoClient(MONGO_URI)

db = client["test"]

patients_collection = db["patients"]
prescriptions_collection = db["prescriptions"]
medicines_collection = db["medicines"]

print("CONNECTED DB:", db.name)
