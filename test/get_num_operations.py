import requests
import json
import sys

addr="GDJELROP5MRTF5QXPW3AKGJSHQQXKEB5AKHTBBYVGOOSZLHPLH4QRBDU"
url="https://horizon.stellar.org/accounts/"


def main(purl, paddr):
	global addr, url

	if purl is not None:
		url=purl+"/accounts/"
	if paddr is not None:
		addr=paddr

	#print(addr)
	#print(url)

	res=requests.get(url+addr+"/operations?limit=200")
	res_json=json.loads(res.text)

	count=process_res(res_json)

	new_res=requests.get(res_json["_links"]["next"]["href"])
	new_res_json=json.loads(res.text)

	while check_valid(res_json, new_res_json):
		count=count+process_res(new_res_json)

		res_json=new_res_json
		new_res=requests.get(res_json["_links"]["next"])
		new_res_json=json.loads(new_res)

	return count


def process_res(res_json):
	#res_json=json.loads(res.text)
	count=0
	for record in res_json["_embedded"]["records"]:
		if record["type"] is "create_account":
			pass
		else:
			count=count+1
	return count


def check_valid(last_res, current_res):
	if last_res is None:
		return True
	else:
		if last_res["_links"]["next"]["href"] is last_res["_links"]["next"]["href"]:
			return False
		else:
			return True



if __name__=="__main__":
	if len(sys.argv) == 2:
		addr=sys.argv[1]
	elif len(sys.argv) == 3:
		addr=sys.argv[1]
		url=sys.argv[2] + "/accounts/"
	
	print(main(None, None))
	