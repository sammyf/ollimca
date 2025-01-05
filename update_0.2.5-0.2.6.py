from ollimca_core import config
import sqlite3

cfg = config.Config().ReadConfig()

conn = sqlite3.connect(cfg['db']['sqlite_path'])

cursor = conn.cursor()
cursor.execute('alter table images add persons_ids TEXT;')
cursor.execute("""
create table persons
(
    id       integer not null
        constraint id
            primary key autoincrement,
    callname TEXT    not null
        constraint persons_pk
            unique
);
""")
conn.commit()
conn.close()

print("Databases updated to 0.2.6")