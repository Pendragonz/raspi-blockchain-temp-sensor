import requests
import unittest
import subprocess
import time
import os
import sqlite3
import json

import get_num_operations

from shutil import copyfile, copytree

from stellar_sdk import Server, Keypair, TransactionBuilder, Network, Account


url="http://0.0.0.0:5050"

class TestHome(unittest.TestCase):
	api=None
	url=None
	HIDE=None

	def setUp(self):
		self.cleanTheSlate()
		self.url="http://0.0.0.0:5050"
		self.HIDE=open(os.devnull, "w")
		#self.api=subprocess.Popen(["flask", "run", "--host", "0.0.0.0", "--port", "5050", "--no-reload"]) #, stdout=self.HIDE#)
		self.api=subprocess.Popen(["python3", "api.py", "5050", "&"], shell=False, stdout=self.HIDE)
		#print("SUBPROCESS STARTED =====================")
		time.sleep(3)

	def tearDown(self):
		self.api.terminate()
		self.api.wait()
		time.sleep(1)
		#print("SUBPROCESS TERMINATED ===============")
		self.cleanTheSlate()
		self.HIDE.close()

	#deletes all api.py artifacts.
	def cleanTheSlate(self):
		try:
			os.remove("users.db")
		except OSError:
			pass

		try:
			os.remove("envdata.db")
		except OSError:
			pass

		try:
			os.remove("keys.txt")
		except OSError:
			pass

		try:
			os.remove("status.txt")
		except OSError:
			pass

		try:
			os.remove("mainrunning.txt")
		except OSError:
			pass

		try:
			os.remove("testnetrunning.txt")
		except OSError:
			pass


	def test_home(self):
		self.assertEqual(requests.get(url+"/").status_code, 200)

	def test_register(self):
		uname="daniel"
		pword="password"

		self.register(uname, pword)
		time.sleep(1)
		self.assertTrue(self.check_uname_in_db(uname))

	def register(self, uname, pword):
		data={'username': str(uname), 'password':str(pword)}
		reg_url=url+"/register_submit"
		requests.post(reg_url, data=data)


	def check_uname_in_db(self, username):
		userdb=sqlite3.connect("users.db")
		curs=userdb.cursor()
		curs.execute('SELECT * FROM users WHERE username=?', [username])
		res=curs.fetchone()
		userdb.close()
		return res



	def test_run_testnet(self):
		uname="daniel"
		pword="password"
		self.register(uname, pword)
		run_url=url+"/run_submit"
		data={'NETWORK': 'TESTNET', 'INTERVAL': '2'}
		res=requests.post(run_url, data=data, auth=(uname, pword))
		#print(res.text)
		self.assertEqual(res.status_code, 200)

		time.sleep(10)
		num_entries = self.get_num_env_entries()
		#print("DB ENTRIES-------------------------------------------"+str(num_entries))
		self.assertTrue(int(num_entries) > 3)

		pubkey=self.get_pubkey_from_file()
		#print("PUBKEY----------------------------------------------------"+pubkey)
		if pubkey is not None:
			num_operations=get_num_operations.main("https://horizon-testnet.stellar.org", pubkey)
			#print("NUM OPERATIONS---------" + str(num_operations))
			self.assertTrue(num_operations > 1)

		requests.get(url+"/reset", auth=(uname,pword))


	def get_pubkey_from_file(self):
		if os.path.isfile("keys.txt") is True:
			with open("keys.txt", "r") as f:
				keys=[x.strip() for x in f.read().split(",")]
				return keys[1]
		else:
			return None


	def get_keypair_from_file(self, fname):
		with open(fname, "r") as f:
			keyinfo=[x.strip() for x in f.read().split(",")]
			keys = Keypair.from_secret(keyinfo[2])
		return keys


	def get_num_env_entries(self):
		envdata=sqlite3.connect('envdata.db')
		c=envdata.cursor()
		c.execute('SELECT Count(*) FROM ENV')
		res=c.fetchone()
		envdata.close()
		return res[0]


	def test_run_mainnet(self):
		uname="daniel"
		pword="password"
		self.register(uname, pword)
		dta={'NETWORK': 'MAINNET', 'INTERVAL': '2'}
		requests.post(url+"/run_submit", data=dta, auth=(uname,pword))
		time.sleep(2)
		test_keys=self.get_keypair_from_file('testing_keys.txt')
		serv_keys=self.get_keypair_from_file('keys.txt')
		self.send_txn(test_keys.secret, serv_keys.public_key, None)
		time.sleep(30)

		self.assertTrue(self.get_num_env_entries() > 3)


		#stop server before testing and refunding acc to give horizon time.
		#horizon returns false sequence numbers during high load
		requests.get(url+'/reset', auth=(uname, pword))

		time.sleep(5)

		num_operations=get_num_operations.main("https://horizon.stellar.org", serv_keys.public_key)

		#print("NUM STELLAR TXNS"+str(num_operations))
		self.assertTrue(num_operations>1)

		#refund src account
		self.send_txn(serv_keys.secret, test_keys.public_key, True)


	def test_reset(self):
		uname="daniel"
		pword="password"
		self.register(uname, pword)
		dta={'NETWORK':'TESTNET','INTERVAL':'2'}
		requests.post(url+'/run_submit', data=dta, auth=(uname,pword))
		time.sleep(20)
		entries=self.get_num_env_entries()
		self.assertTrue(entries>=3)
		requests.get(url+'/reset', auth=(uname,pword))

		time.sleep(2)
		userdb=sqlite3.connect("users.db")
		curs=userdb.cursor()
		curs.execute('SELECT Count(*) FROM users')
		numUsers=curs.fetchone()
		userdb.close()
		print("number of users::::::::::::" + str(numUsers[0]))
		self.assertEqual(numUsers[0], 0)



	def test_refund(self):
		uname="daniel"
		pword="password"
		self.register(uname,pword)
		dta={'NETWORK':'MAINNET','INTERVAL':'3'}
		requests.post(url+'/run_submit', data=dta, auth=(uname,pword))
		time.sleep(20)

		test_keypair=self.get_keypair_from_file('testing_keys.txt')
		serv_keypair=self.get_keypair_from_file('keys.txt')

		dta={'CONFIRM':'YES'}
		requests.post(url+'/refund_confirm',data=dta, auth=(uname,pword))
		time.sleep(5)
		
		uri="https://horizon.stellar.org/accounts/"+test_keypair.public_key
		uri=uri+"/operations?order=desc"
		res=requests.get(uri)
		res_json=json.loads(res.text)
		record=res_json["_embedded"]["records"][0]
		self.assertEqual(record["type"],"account_merge")
		#self.assertEqual(record["source_account"], serv_keypair.public_key)
		self.assertEqual(record["into"], test_keypair.public_key)


	#origin= source private key, dest = destination stellar pubkey
	#merge boolean. if True, source acc merges with destination
	def send_txn(self, origin, dest, merge):
		keys=Keypair.from_secret(origin)
		server=Server("https://horizon.stellar.org/")
		NET_PASS=Network.PUBLIC_NETWORK_PASSPHRASE
		basefee=server.fetch_base_fee()
		account=server.load_account(keys.public_key)
		#print("DESTINATION:-----------------------------------:" + dest)
		if merge !=  None and merge == True:
			txn=TransactionBuilder(
				source_account=account,
				network_passphrase=NET_PASS,
				base_fee=basefee,
					).append_account_merge_op(
					destination=dest
					).set_timeout(10000).build()
		else:
			#print("POPULATING ACCOUNT: "+dest+ "from: " + keys.public_key)
			txn=TransactionBuilder(
				source_account=account,
				network_passphrase=NET_PASS,
				base_fee=basefee,
				).append_create_account_op(
					destination=dest,
					starting_balance="1.51").set_timeout(1000).build()
		txn.sign(keys)
		server.submit_transaction(txn)


	def test_get_pubkey(self):
		uname="daniel"
		pword="password"
		self.register(uname, pword)
		data={'NETWORK': 'TESTNET', 'INTERVAL': '2'}
		requests.post(url+"/run_submit", data=data, auth=(uname,pword))
		res=requests.get(url+"/get/pubkey")

		proc_res=res.text.split(": ")
		self.assertEqual(proc_res[0], "TESTNET")

		pubkey=self.get_pubkey_from_file()

		self.assertEqual(proc_res[1], pubkey)

		requests.get(url+'/reset', auth=(uname, pword))


copyfile('../api.py', 'api.py')
copyfile('../read.py', 'read.py')
copyfile('../write.py','write.py')
try:
	copytree('../templates', 'templates')
except Exception as e:
	pass

unittest.main()