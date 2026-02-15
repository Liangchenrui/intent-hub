echo "======= 实验环境报告 =======" > env_report.txt
echo "日期: $(date)" >> env_report.txt

# 1. 操作系统信息
echo - e "\n[OS Version]" >> env_report.txt
lsb_release - d | awk - F':\t' '{print $2}' >> env_report.txt

# 2. CPU 与 内存
echo - e "\n[Hardware]" >> env_report.txt
lscpu | grep "Model name" | awk - F':  +' '{print $2}' >> env_report.txt
free - h | grep "Mem:" | awk '{print "Total RAM: "$2}' >> env_report.txt

# 3. GPU 信息 (如果适用)
if command - v nvidia-smi & > / dev/null
then
echo - e "\n[GPU]" >> env_report.txt
nvidia-smi - -query-gpu = gpu_name, driver_version, memory.total - -format = csv, noheader >> env_report.txt
fi

# 4. 关键软件版本
echo - e "\n[Software]" >> env_report.txt
python - -version 2 > &1 >> env_report.txt
gcc - -version | head - n 1 >> env_report.txt
if command - v nvcc & > / dev/null
then
nvcc - -version | grep "release" >> env_report.txt
fi

echo "报告已生成: env_report.txt"
