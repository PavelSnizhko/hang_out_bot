import sqlite3

class SQLWorker:

    def __init__(self, database):
        self.connection = sqlite3.connect(database, check_same_thread=False)
        self.cursor = self.connection.cursor()

    def set_up(self):
        with self.connection:
            tblstmt = "CREATE TABLE IF NOT EXISTS place( id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,photo TEXT,latitude INTEGER NOT NULL,longitude INTEGER NOT NULL, title text)"
            itemidx = "CREATE INDEX IF NOT EXISTS userIndex ON place (user_id ASC)"
            self.cursor.execute(tblstmt)
            self.cursor.execute(itemidx)



    def insert_new_place(self, data):
        with self.connection:
            stmt = "INSERT INTO place (user_id, title, photo, latitude, longitude) VALUES (?, ?, ?, ?, ?)"
            args = (data['user_id'], data['title'], data['photo'], data['latitude'], data['longitude'])
            self.cursor.execute(stmt, args)


    def select_all(self, user_id):
        """ Получаем все строки """
        with self.connection:
            return self.cursor.execute('SELECT * FROM place where user_id=?', (user_id, )).fetchall()

    def select_one_record(self, user_id):
        """ Получаем одну строку с номером row_num """
        with self.connection:
            return self.cursor.execute('SELECT * FROM place WHERE id = ?', (user_id,)).fetchall()[0]

    def select_ten_records(self, user_id):
        with self.connection:
            tem_result = self.cursor.execute('SELECT * FROM place where user_id = ? ORDER BY id ASC LIMIT 10', (user_id,))
            result = tem_result.fetchall()
            return result

    def count_all_records(self, user_id):
        """ Считаем количество строк """
        with self.connection:
            result = self.cursor.execute('SELECT * FROM place where user_id=?', (user_id,)).fetchall()
            return len(result)

    def remove_all_records(self, user_id):
        with self.connection:
            self.cursor.execute('Delete from place where user_id = ?', (user_id,))



    def close(self):
        """ Закрываем текущее соединение с БД """
        self.connection.close()

