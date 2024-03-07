import argparse
import multiprocessing
import os
import time
import sys
from pathlib import Path
from crowd_count import CrowdCount

def slave_main(config_file):
    print(f"以配置文件 {config_file} 运行slave进程")
    crowd_counter = CrowdCount(config_file)
    crowd_counter.run()

def start_slave_process(config_file):
    return multiprocessing.Process(target=slave_main, args=(config_file,))

def master_main(config_dir):
    # 获取配置目录下所有JSON配置文件
    config_files = [str(f) for f in Path(config_dir).glob('*.json')]
    slaves = {}

    # 为每个配置文件启动一个slave进程
    for config_file in config_files:
        p = start_slave_process(config_file)
        p.start()
        slaves[p.pid] = (p, config_file)

    try:
        while True:
            time.sleep(1)
            for pid in list(slaves.keys()):
                p, config_file = slaves[pid]
                if not p.is_alive():
                    print(f"重启slave进程 {pid}，配置文件为: {config_file}")
                    p = start_slave_process(config_file)
                    p.start()
                    del slaves[pid]
                    slaves[p.pid] = (p, config_file)
    except KeyboardInterrupt:
        print("Master进程退出，终止所有slave进程...")
        for p, _ in slaves.values():
            p.terminate()
        for p, _ in slaves.values():
            p.join()

def main():
    parser = argparse.ArgumentParser(description="启动master或slave进程。")
    parser.add_argument("--mode", choices=["master", "slave"], default="master", help="运行模式")
    parser.add_argument("--config", help="对于slave模式，需要指定配置文件路径；对于master模式，需要指定配置文件目录路径。")
    args = parser.parse_args()

    if args.mode == "master":
        if not args.config or not Path(args.config).is_dir():
            print("错误：Master模式需要指定包含配置文件的目录路径。")
            sys.exit(1)
        master_main(args.config)
    elif args.mode == "slave":
        if not args.config or not Path(args.config).is_file():
            print("错误：Slave模式需要指定配置文件路径。")
            sys.exit(1)
        slave_main(args.config)
    else:
        print("错误：无效的模式或配置。")
        sys.exit(1)

if __name__ == "__main__":
    main()
