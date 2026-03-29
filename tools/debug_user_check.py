import json

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

# ดึง username จาก following
following_set = set()
if isinstance(following_data, dict) and 'relationships_following' in following_data:
    items = following_data['relationships_following']
else:
    items = following_data

for item in items:
    if isinstance(item, dict) and 'title' in item and item['title']:
        following_set.add(item['title'])

# ตรวจสอบคนที่อยู่ใน following บางคน
test_users = ['pum_surapha', 'rcrtl_chane', 'wlp_phi6', 'aommuaommuu', 'charavi83']

print("=== ตรวจสอบรายชื่อเฉพาะ ===")
for user in test_users:
    in_following = user in following_set
    in_followers = user in followers_set
    print(f"{user}:")
    print(f"  - ฉันฟอลคนนี้: {in_following}")
    print(f"  - คนนี้ฟอลฉันกลับ: {in_followers}")
    if in_following and not in_followers:
        print("  -> ⚠️ ไม่ follow back")
    elif in_following and in_followers:
        print("  -> ✅ follow back แล้ว")
    print()

# ดูคนที่ follow กลับทั้งหมด
mutual = following_set & followers_set
print(f"จำนวนคนที่ follow กลับ: {len(mutual)} คน")
print(f"จำนวนคนที่ไม่ follow กลับ: {len(following_set - followers_set)} คน")
print(f"คำนวณ: {len(mutual)} + {len(following_set - followers_set)} = {len(following_set)}")
