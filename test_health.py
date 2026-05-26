import time
from health_monitor import HealthMonitor

def test():
    hm = HealthMonitor(sample_interval=0.5)
    hm.start()
    print("HealthMonitor started.")
    time.sleep(1)

    # Allocate a large block of memory to trigger it
    print("Allocating memory...")
    try:
        a = [0] * (50 * 1024 * 1024) # ~400MB list (each element is 8 bytes in 64-bit python)
    except MemoryError:
        pass

    time.sleep(1)
    print("Test finished.")
    hm.stop()

if __name__ == "__main__":
    test()
