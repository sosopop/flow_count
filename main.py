import argparse
import threading
import time
import sys
from pathlib import Path
from flow_count import FlowCount

def slave_main(config_file):
    print(f"以配置文件 {config_file} 运行slave线程")
    flow_count = FlowCount(config_file)
    flow_count.run()

def start_slave_thread(config_file):
    return threading.Thread(target=slave_main, args=(config_file,))

def master_main(config_dir):
    # 获取配置目录下所有JSON配置文件
    config_files = [str(f) for f in Path(config_dir).glob('*.json')]
    slaves = {}

    # 为每个配置文件启动一个slave线程
    for config_file in config_files:
        t = start_slave_thread(config_file)
        t.start()
        slaves[t.ident] = (t, config_file)
        time.sleep(5)

    print("running ...")
    for t, _ in slaves.values():
        t.join()


def main():
    parser = argparse.ArgumentParser(description="启动master或slave线程。")
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