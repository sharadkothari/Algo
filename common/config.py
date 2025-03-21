from pathlib import Path

server_url = 'http://100.123.122.115'
redis_host = '100.123.122.115'
redis_port = 6379
redis_db = 0
redis_hash = "tick"
redis_stream = "flask_e7270"

base_dir = str(Path(__file__).resolve().parent.parent)
base_dir_prv = str(Path(__file__).resolve().parent.parent.parent.parent / 'Algo')

data_dir = base_dir + '/common/data/'

bhavcopy_dir = base_dir_prv + '/bhavcopy/'


if __name__ == "__main__":
    print(base_dir, base_dir_prv, bhavcopy_dir, data_dir)
    #print(str(Path(__file__).resolve().parent.parent.parent.parent / 'Algo'))
    #print(base_dir_prv)
