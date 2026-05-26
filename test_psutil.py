import psutil
print(psutil.Process().memory_info().rss)
