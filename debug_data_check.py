import json
import os

# โหลดข้อมูล
with open('instagram_data/followers_1.json', 'r', encoding='utf-8') as f:
    followers_data = json.load(f)

with open('instagram_data/following.json', 'r', encoding='utf-8') as f:
    following_data = json.load(f)

# ดึง username จาก followers
followers_set = set()
for item in followers_data:
    if isinstance(item, dict) and 'string_list_data' in item:
        for data in item['string_list_data']:
            if 'value' in data:
                followers_set.add(data['value'])

print(f"จำนวน Followers: {len(followers_set)}")
print(f"ตัวอย่าง Followers 10 คนแรก: {list(followers_set)[:10]}\n")

# ดึง username จาก following
following_set = set()
if isinstance(following_data, dict) and 'relationships_following' in following_data:
    items = following_data['relationships_following']
else:
    items = following_data

for item in items:
    if isinstance(item, dict) and 'title' in item and item['title']:
        following_set.add(item['title'])

print(f"จำนวน Following: {len(following_set)}")
print(f"ตัวอย่าง Following 10 คนแรก: {list(following_set)[:10]}\n")

# หาคนที่ไม่ follow back
unfollowers = following_set - followers_set
print(f"จำนวนคนที่ไม่ follow back: {len(unfollowers)}")
print("ตัวอย่าง 20 คนแรกที่ไม่ follow back:")
for i, username in enumerate(list(unfollowers)[:20], 1):
    print(f"{i}. {username}")

# เช็คตัวอย่าง: เลือก 5 คนแรกที่ไม่ follow back มาดูว่ามีใน followers จริงไหม
print("\n=== ตรวจสอบรายละเอียด ===")
for username in list(unfollowers)[:5]:
    in_followers = username in followers_set
    in_following = username in following_set
    print(f"{username}: in_followers={in_followers}, in_following={in_following}")
    
    # หาใน followers แบบไม่สน case
    followers_lower = {f.lower() for f in followers_set}
    print(f"  -> ถ้าไม่สน case: {username.lower() in followers_lower}")
