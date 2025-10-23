
import json

def load_json(file_path):
    try :
        with open(file_path , 'r') as f : 
            return json.load(f)
    
    except Exception as e  :
            print(f"error{e}")


def category_viwed(id , file_path):
     data= load_json(file_path)
     if id  == data['id'] and data["success"] == True :
      data = load_json(file_path)
      temp = [{"category_viewed": ""},{"recentaly_purchased": ""}]
      temp[0]["category_viewed"] = data["product_category(viewed)"]
      temp[1]["recentaly_purchased"] = data["purchased"]
      
      