import json
from database import x
def log(actor,action,obj_type=None,obj_id=None,details=None):
    x('INSERT INTO audit_logs(actor_id,action,object_type,object_id,details) VALUES(?,?,?,?,?)',(actor,action,obj_type,obj_id,json.dumps(details,ensure_ascii=False) if isinstance(details,(dict,list)) else details))
