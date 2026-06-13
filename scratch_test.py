from passlib.hash import bcrypt
try:
    h = bcrypt.hash("admin123")
    print("Hash success:", h)
except Exception as e:
    import traceback
    traceback.print_exc()
