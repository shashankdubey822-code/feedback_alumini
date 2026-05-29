import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()
conn=psycopg2.connect(os.environ['DATABASE_URL'])
cur=conn.cursor()
cur.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS form_url TEXT, ADD COLUMN IF NOT EXISTS form_edit_url TEXT")
conn.commit()
print('Done')
