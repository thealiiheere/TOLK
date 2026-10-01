"""
Utility script to reset and seed test data for TOLK MVP.
Pre-seeded accounts:
- 1 Admin: +998901110001 (Администратор TOLK)
- 2 Tutors: 
  * +998902220001 (Алишер Каримов, Русский язык)
  * +998902220002 (Дильноза Рахимова, Корейский язык)
- 5 Students in test group (Group #1):
  * +998903330001 (Сардор Алиев, 0 страйков)
  * +998903330002 (Малика Юсупова, 1 страйк)
  * +998903330003 (Джасур Умаров, 2 страйка)
  * +998903330004 (Нигора Ахмедова, 3 страйка — блокировка)
  * +998903330005 (Темур Саидов, 0 страйков)
- Additional pending payment students for Admin demo verification
"""
import os
from app.database import DB_PATH, init_db, seed_demo_data

def reset_and_seed():
    if DB_PATH.exists():
        os.remove(DB_PATH)
        print(f"Removed existing database at {DB_PATH}")
    init_db()
    seed_demo_data()
    print("Database freshly initialized and pre-seeded with test accounts!")

if __name__ == "__main__":
    reset_and_seed()
