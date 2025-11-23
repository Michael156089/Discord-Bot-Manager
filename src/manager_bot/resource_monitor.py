import psutil
import asyncio
from collections import defaultdict

# limits
max_cpu = 80.0
max_ram = 100

violations = defaultdict(int)

def get_resources(pid):
    try:
        p = psutil.Process(pid)
        cpu = p.cpu_percent(interval=1.0)
        mem = p.memory_info().rss / (1024 * 1024)
        return {"cpu": cpu, "ram": mem}
    except:
        return None

def check_limits(user_id, bot_name, pid):
    res = get_resources(pid)
    if not res:
        return False, ""
        
    key = (user_id, bot_name)
    if res["cpu"] > max_cpu or res["ram"] > max_ram:
        violations[key] += 1
        if violations[key] >= 3:
            return True, f"Too much CPU ({res['cpu']}%) or RAM ({res['ram']}MB)"
    else:
        if key in violations:
            violations[key] = 0
    return False, ""

def clear_violations(user_id, bot_name):
    if (user_id, bot_name) in violations:
        del violations[(user_id, bot_name)]

async def monitor_bot_resources(active_processes, bot):
    await asyncio.sleep(30)
    while True:
        await asyncio.sleep(15)
        for key, (proc, _) in list(active_processes.items()):
            if proc.returncode is not None:
                continue
                
            kill, reason = check_limits(key[0], key[1], proc.pid)
            if kill:
                print(f"Killing {key[1]} for resources: {reason}")
                try:
                    proc.terminate()
                    clear_violations(key[0], key[1])
                    # notify user
                    user = bot.get_user(key[0])
                    if user:
                        await user.send(f"Bot {key[1]} stopped: {reason}")
                except:
                    pass
