# Utilisation de PyMySQL (pur Python) comme pilote MySQL.
# Idéal pour cPanel/hébergement mutualisé où mysqlclient ne compile pas.
import pymysql

pymysql.install_as_MySQLdb()
