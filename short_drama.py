# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os, json, random, time, shutil, requests, asyncio, datetime, math
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import *
from moviepy.audio.fx.all import audio_loop
import edge_tts
from docx import Document

# ===================== 用户配置区 =====================
MAX_EPISODES = 88
SCENES_PER_EPISODE = 25
SECONDS_PER_SCENE = 3.6
FPS = 24
IMAGE_SIZE = (1080, 1920)
OUTPUT_DIR = "Temp_Media"
STATE_FILE = "drama_state.json"
SILENCE_MP3 = "silence.mp3"
REPORT_BASE = "Reports"
KEEP_IMAGES_IN_REPORT = 3

DRAMA_TITLE = "肖鹏修仙：开局被退婚，我逆袭成神"
DRAMA_DESC = ("肖鹏穿越修仙界，开局就被退婚、被逐出师门，所有人都说他是废柴。"
              "可他身上藏着上古神格'暴君'，每受一次羞辱就觉醒一层封印！"
              "当仇家杀上门、宗门跪求他回去时，肖鹏只说了一句：晚了。"
              "88集逆袭之路，从被人踩在脚下到一剑斩断苍穹——你以为他输定了？"
              "不，这才是他封神的开始！")

# ===================== 人物设定 =====================
MAIN_CHARACTER = {
    "name": "肖鹏",
    "gender": "男性",
    "age": "20岁",
    "face": "剑眉星目，左脸有一道浅疤，坚毅冷峻",
    "body": "修长挺拔，身形匀称，肌肉线条分明",
    "hair": "黑色长发束起",
    "clothes": "蓝色道袍，衣摆有云纹刺绣",
    "style": "古风修仙者"
}

SIDE_CHARACTERS = {
    "师尊": {
        "gender": "男性",
        "age": "60岁",
        "face": "白发白须，面容慈祥但眼神锐利",
        "body": "清瘦仙风道骨",
        "clothes": "白色道袍，手持拂尘",
        "style": "得道高人"
    },
    "未婚妻": {
        "gender": "女性",
        "age": "18岁",
        "face": "瓜子脸，丹凤眼，樱唇皓齿",
        "body": "纤瘦婀娜",
        "clothes": "红色嫁衣，金玉配饰",
        "style": "世家千金"
    },
    "反派师兄": {
        "gender": "男性",
        "age": "25岁",
        "face": "阴鸷狡诈，鹰钩鼻，薄唇",
        "body": "高大魁梧",
        "clothes": "黑色劲装，银线绣蟒",
        "style": "狠辣反派"
    },
    "神秘老者": {
        "gender": "男性",
        "age": "70岁",
        "face": "满面红光，鹤发童颜",
        "body": "微胖富态",
        "clothes": "金色锦袍，珠宝满身",
        "style": "富商大贾"
    },
    "小师妹": {
        "gender": "女性",
        "age": "16岁",
        "face": "圆脸大眼，笑容甜美",
        "body": "娇小玲珑",
        "clothes": "粉色衣裙，双丫髻",
        "style": "天真可爱"
    }
}

# ===================== 匿名模式参数 =====================
IMAGE_INTERVAL = 20.0
AUDIO_INTERVAL = 5.0
RETRY_INTERVAL = 20.0
EPISODE_INTERVAL = 5
AUDIO_RETRIES = 3
IMAGE_TIMEOUT = 120
MAX_IMAGE_RETRIES = 5
MAX_AUDIO_RETRIES = 3
USE_PLACEHOLDER = False

# ===================== 状态管理 =====================
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"episode": 0, "last_ending": ""}
    return {"episode": 0, "last_ending": ""}

def save_state(ep, ending):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump({"episode": ep, "last_ending": ending}, f, ensure_ascii=False, indent=2)

# ===================== 增强版提示词构建（特效前置） =====================
def build_character_prompt(scene_desc, emotion="平静", action="站立", 
                          characters=[], special_effects=""):
    # 基础风格（加强视觉冲击）
    base_style = ("Chinese comic style, dramatic, vertical 9:16, high detail, "
                  "cinematic lighting, masterpiece, best quality, intricate details, "
                  "realistic rendering, dynamic composition, 4k, 8k, high resolution, "
                  "professional illustration, digital painting, vibrant colors, "
                  "dramatic shadows, intense action, glowing effects, explosive energy")
    
    # 角色描述
    char_descs = []
    for char_name in characters:
        if char_name == "主角":
            char = MAIN_CHARACTER
            desc = (f"main character {char['name']}, {char['gender']}, {char['age']}, "
                   f"face: {char['face']}, body: {char['body']}, hair: {char['hair']}, "
                   f"wearing {char['clothes']}, {char['style']} style, ")
            char_descs.append(desc)
        elif char_name in SIDE_CHARACTERS:
            char = SIDE_CHARACTERS[char_name]
            desc = (f"side character {char_name}, {char['gender']}, {char['age']}, "
                   f"face: {char['face']}, body: {char['body']}, "
                   f"wearing {char['clothes']}, {char['style']} style, ")
            char_descs.append(desc)
    
    emotion_action = f"{emotion} expression, {action} posture, "
    
    # 特效放在最前面，并添加强调词
    effects = f"{special_effects}, dazzling visual effects, energy burst, magical glow, " if special_effects else ""
    
    camera_details = ("close-up shot on character's face and hands, "
                     "detailed facial features, dramatic shadows, depth of field, "
                     "cinematic composition, rule of thirds, "
                     "focus on eyes and gestures, dynamic angle, "
                     "action lines, speed lines, impact effect")
    
    # 组合提示词（特效放首位）
    full_prompt = (f"{effects}"
                   f"{scene_desc[:80]}, "
                   f"{''.join(char_descs)[:200]}"
                   f"{emotion_action}"
                   f"{camera_details}, "
                   f"{base_style}")[:500]
    return full_prompt

def generate_skill_effect(skill_type="剑法"):
    effects = {
        "剑法": ["金光剑气纵横", "剑影如龙", "剑芒破空", "万剑齐发", "剑气形成屏障"],
        "掌法": ["掌风如雷", "金色掌印虚空凝聚", "能量波纹扩散", "地面龟裂", "狂风肆虐"],
        "法术": ["火焰滔天", "冰霜蔓延", "闪电劈落", "光华万丈", "元素漩涡"],
        "体术": ["肌肉暴起", "残影连击", "音爆气浪", "重拳破空", "腿鞭如电"],
        "防御": ["金光护体", "能量罩抵御攻击", "符文环绕", "太极图案旋转", "空间扭曲"],
        "爆发": ["气势如虹", "天地变色", "能量喷涌", "光柱冲天", "封印解除"]
    }
    return random.choice(effects.get(skill_type, effects["剑法"]))

# ===================== 增强版剧本生成 =====================
class ScriptGen:
    def __init__(self, last_ending=""):
        self.last_ending = last_ending
        self.scene_counter = 0
    
    def generate(self, topic="修仙"):
        # ------ 增强版场景模板（更生动、更有画面感） ------
        enhanced_templates = [
            {"visual": "肖鹏立于峭壁之巅，狂风卷起他的蓝色道袍，他目光如电，凝视远方滚滚雷云", 
             "emotion": "决绝", "action": "负手而立，衣袂翻飞", 
             "characters": ["主角"], "skill": "", "scene_type": "独白"},
            
            {"visual": "肖鹏与反派师兄正面交锋，双剑碰撞迸射出刺眼火花，四周碎石被气浪震飞", 
             "emotion": "愤怒", "action": "挥剑猛攻，虎口震裂", 
             "characters": ["主角", "反派师兄"], "skill": "剑法", "scene_type": "对决"},
            
            {"visual": "肖鹏被未婚妻当众羞辱，退婚书狠狠甩在脸上，周围人群指指点点，他却攥紧双拳，指甲掐入掌心", 
             "emotion": "屈辱", "action": "咬牙隐忍，血从指缝滴落", 
             "characters": ["主角", "未婚妻"], "skill": "", "scene_type": "羞辱"},
            
            {"visual": "师尊在月光下向肖鹏传授禁忌之术，指尖金光如丝线般缠绕两人，灵气波动扭曲了空气", 
             "emotion": "专注", "action": "盘膝闭目，双手结印", 
             "characters": ["主角", "师尊"], "skill": "法术", "scene_type": "指导"},
            
            {"visual": "肖鹏在秘境中遭巨型妖兽扑杀，他侧身翻滚，剑气横扫，妖兽鳞甲碎片四溅，鲜血染红地面", 
             "emotion": "决绝", "action": "侧身闪避，反手斩击", 
             "characters": ["主角"], "skill": "剑法", "scene_type": "战斗"},
            
            {"visual": "小师妹跌跌撞撞跑来，将一瓶丹药塞进肖鹏手中，满眼担忧：“师兄，你受伤了！”", 
             "emotion": "感激", "action": "轻抚她头，微笑咽下丹药", 
             "characters": ["主角", "小师妹"], "skill": "", "scene_type": "温情"},
            
            {"visual": "神秘老者凭空现身，掌心悬浮一枚金色符文，他低声道：“这就是你体内的上古神格……”", 
             "emotion": "震惊", "action": "瞳孔骤缩，手捂胸膛", 
             "characters": ["主角", "神秘老者"], "skill": "", "scene_type": "揭露"},
            
            {"visual": "肖鹏被仇家围攻，身中数剑，他跪倒在地，眼前闪回师尊训诫，随即体内爆发出一股金色能量，震飞所有敌人", 
             "emotion": "顿悟", "action": "眼中金光迸射，身体悬浮", 
             "characters": ["主角"], "skill": "爆发", "scene_type": "突破"},
            
            {"visual": "肖鹏孤身面对百名修士，他仰天长啸，手中长剑化作千道剑影，如暴雨般倾泻而下，敌军溃散", 
             "emotion": "傲然", "action": "挥剑指天，剑芒万丈", 
             "characters": ["主角"], "skill": "剑法", "scene_type": "碾压"},
            
            {"visual": "肖鹏被暗算倒下，胸口插着一柄毒刃，他颤抖着拔出来，鲜血喷涌，但他眼中燃烧着不甘", 
             "emotion": "痛苦", "action": "咬牙拔出毒刃，单膝跪地", 
             "characters": ["主角"], "skill": "", "scene_type": "危机"},
            
            {"visual": "肖鹏在山洞中醒来，发现自己被锁链缠绕，他挣扎中体内神格共鸣，锁链寸寸断裂，金光炸裂洞壁", 
             "emotion": "狂热", "action": "仰天怒吼，挣脱锁链", 
             "characters": ["主角"], "skill": "爆发", "scene_type": "高潮"},
            
            {"visual": "肖鹏与师尊并肩作战，两人剑气合璧，化作青龙虚影，直冲云霄，天穹都为之撕裂", 
             "emotion": "威严", "action": "与师尊同时出剑，剑势如龙", 
             "characters": ["主角", "师尊"], "skill": "剑法", "scene_type": "战斗"},
            
            {"visual": "肖鹏在悬崖边救回落入深渊的小师妹，两人悬在半空，他手臂青筋暴起，用尽最后力气将她甩回崖顶，自己却坠落", 
             "emotion": "英勇", "action": "单手拉住小师妹，另一手攀岩", 
             "characters": ["主角", "小师妹"], "skill": "", "scene_type": "温情"},
            
            {"visual": "肖鹏发现反派师兄竟然是自己的亲哥哥，两人对视，空气凝固，脚下地面开始龟裂", 
             "emotion": "震惊", "action": "剑尖颤抖，泪光闪烁", 
             "characters": ["主角", "反派师兄"], "skill": "", "scene_type": "揭露"},
            
            {"visual": "肖鹏在雷劫中沐浴，天雷不断劈落，他却吸收雷霆之力，周身雷光缠绕，宛如雷神降世", 
             "emotion": "坚毅", "action": "张开双臂，迎接天雷", 
             "characters": ["主角"], "skill": "法术", "scene_type": "突破"},
        ]
        
        scene_templates = enhanced_templates
        self.scene_counter += 1
        offset = (self.scene_counter // 2) % len(scene_templates)
        
        script = []
        for i in range(SCENES_PER_EPISODE):
            template = scene_templates[(i + offset) % len(scene_templates)]
            # 构造细节
            scene_detail = f"{template['visual']}"
            ambiance = random.choice(["，空气仿佛凝固", "，远处传来雷鸣", "，周围灵气躁动", "，时间仿佛变慢"])
            scene_detail += ambiance
            
            if template['scene_type'] in ["战斗", "对决", "碾压", "高潮"]:
                skill_desc = generate_skill_effect(template.get('skill', '剑法'))
                scene_detail += f"，{skill_desc}炸裂四散"
            
            visual_desc = scene_detail
            # 旁白改为更具文学性的描述，加入心理活动
            emotion_words = {
                "愤怒": "他怒不可遏，眼中燃烧着复仇之火",
                "决绝": "他已将生死置之度外，只有一往无前",
                "屈辱": "这份耻辱，他铭记在心，誓要百倍奉还",
                "专注": "心神合一，外界一切都已消失",
                "感激": "心中暖流涌动，这份恩情他不敢忘",
                "震惊": "这真相如同惊雷，将他劈得头晕目眩",
                "顿悟": "刹那间，无数明悟涌入心间，境界松动",
                "傲然": "他嘴角扬起一抹冷笑，视众生如蝼蚁",
                "痛苦": "剧痛袭来，但他咬牙撑住，决不倒下",
                "狂热": "他血脉贲张，体内的力量渴望释放",
                "威严": "他发出龙吟般的咆哮，气势震天",
                "英勇": "他义无反顾，即便牺牲自己也在所不惜",
                "坚毅": "天劫又如何，他偏要逆天而行"
            }
            emotion_desc = emotion_words.get(template['emotion'], "")
            narration = f"{emotion_desc}。{visual_desc}"
            
            chars = template.get('characters', ["主角"])
            emotion = template.get('emotion', "平静")
            action = template.get('action', "站立")
            skill = template.get('skill', "")
            
            skill_effect = ""
            if skill and template['scene_type'] in ["战斗", "对决", "碾压", "突破", "高潮"]:
                skill_effect = f"使用{skill}，{generate_skill_effect(skill)}，光芒四射，能量波扩散"
            elif template['scene_type'] == "危机":
                skill_effect = "身负重伤，但眼神如刀，迸发出最后的潜力"
            elif template['scene_type'] == "突破":
                skill_effect = "天地共鸣，灵气如漩涡般汇聚，他境界突破，金光护体"
            
            script.append({
                "scene": i+1,
                "visual": visual_desc,
                "narration": narration,
                "characters": chars,
                "emotion": emotion,
                "action": action,
                "skill": skill,
                "skill_effect": skill_effect,
                "scene_type": template['scene_type'],
                "prompt": build_character_prompt(
                    visual_desc, emotion, action, chars, skill_effect
                )
            })
        
        return script

# ===================== 静音文件 =====================
def create_silence():
    if not os.path.exists(SILENCE_MP3):
        try:
            from moviepy.audio.AudioClip import AudioClip
            silence = AudioClip(lambda t: [0, 0], duration=0.5)
            silence.write_audiofile(SILENCE_MP3, fps=24000, verbose=False, logger=None)
            print("✅ 静音文件创建成功")
        except Exception as e:
            print(f"⚠️ 静音文件创建失败: {e}")

# ===================== 图片生成 =====================
def generate_image(prompt, save_path):
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=1080&height=1920&nologo=true"
    start_time = time.time()
    
    for attempt in range(MAX_IMAGE_RETRIES):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
            }
            r = requests.get(url, timeout=IMAGE_TIMEOUT, headers=headers)
            elapsed = time.time() - start_time
            
            if r.status_code == 200 and len(r.content) > 10000:
                try:
                    img = Image.open(io.BytesIO(r.content))
                    if img.size[0] >= 500 and img.size[1] >= 500:
                        with open(save_path, 'wb') as f:
                            f.write(r.content)
                        print(f"✅ 成功 (尝试{attempt+1}, {elapsed:.1f}s)")
                        return {"path": save_path, "prompt": prompt[:100], "url": url, 
                                "status": "success", "time": elapsed, "retries": attempt}
                except Exception as e:
                    print(f"⚠️ 解析失败: {e}")
            elif r.status_code == 429:
                print(f"⚠️ 触发限流(429)，等待后重试...")
            elif r.status_code == 503:
                print(f"⚠️ 服务暂时不可用(503)，等待后重试...")
            else:
                print(f"⚠️ 状态码 {r.status_code}，内容大小 {len(r.content)}")
        except Exception as e:
            print(f"⚠️ 请求异常: {e}")
        
        if attempt < MAX_IMAGE_RETRIES - 1:
            wait = RETRY_INTERVAL * (attempt + 1)
            print(f"⏳ 等待 {wait:.1f}s 后第{attempt+2}次重试...")
            time.sleep(wait)
    
    elapsed = time.time() - start_time
    print(f"❌ 所有{MAX_IMAGE_RETRIES}次重试均失败")
    
    if USE_PLACEHOLDER:
        img = Image.new('RGB', IMAGE_SIZE, (30, 30, 80))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("simhei.ttf", 50)
        except:
            font = ImageFont.load_default()
        draw.text((200, 300), "修仙者", fill=(255, 255, 255), font=font)
        draw.text((200, 1500), "自动短剧", fill=(255, 200, 0), font=font)
        img.save(save_path)
        print(f"⚠️ 使用占位图")
        return {"path": save_path, "prompt": prompt[:100], "url": url, 
                "status": "placeholder", "time": elapsed, "retries": MAX_IMAGE_RETRIES}
    else:
        return {"path": None, "prompt": prompt[:100], "url": url, 
                "status": "failed", "time": elapsed, "retries": MAX_IMAGE_RETRIES}

# ===================== 配音 =====================
async def gen_audio(text, path):
    if not text or len(text.strip()) < 3:
        shutil.copy(SILENCE_MP3, path)
        return {"path": path, "text": text, "status": "silence", "voice": None, "time": 0, "retries": 0}
    
    voice_list = ["zh-CN-YunxiNeural", "zh-CN-XiaoyiNeural", "zh-CN-YunjianNeural"]
    start_time = time.time()
    
    for attempt in range(MAX_AUDIO_RETRIES):
        voice = random.choice(voice_list)
        try:
            communicate = edge_tts.Communicate(text[:100], voice, rate="+5%")
            await communicate.save(path)
            elapsed = time.time() - start_time
            print(f"✅ 成功 (尝试{attempt+1})")
            return {"path": path, "text": text[:50], "status": "success", "voice": voice, 
                    "time": elapsed, "retries": attempt}
        except Exception as e:
            print(f"⚠️ 失败 (尝试 {attempt+1}/{MAX_AUDIO_RETRIES}): {e}")
            if attempt < MAX_AUDIO_RETRIES - 1:
                wait = RETRY_INTERVAL * (attempt + 1)
                await asyncio.sleep(wait)
    
    elapsed = time.time() - start_time
    print(f"⚠️ 使用静音替代")
    shutil.copy(SILENCE_MP3, path)
    return {"path": path, "text": text[:50], "status": "silence", "voice": None, 
            "time": elapsed, "retries": MAX_AUDIO_RETRIES}

# ===================== 增强版运镜（复合运动） =====================
def apply_camera_motion(clip, duration, scene_type="普通"):
    """
    增强版运镜：支持同时缩放+平移+旋转，并加入随机晃动
    """
    # 根据场景类型调整运动幅度和类型
    if scene_type == "战斗":
        scale_range = (0.10, 0.25)
        pan_range = 0.35
        rot_range = 5.0
        shake_amp = 8
    elif scene_type == "高潮":
        scale_range = (0.08, 0.20)
        pan_range = 0.30
        rot_range = 8.0
        shake_amp = 10
    elif scene_type == "温情":
        scale_range = (0.02, 0.06)
        pan_range = 0.15
        rot_range = 2.0
        shake_amp = 3
    else:
        scale_range = (0.04, 0.10)
        pan_range = 0.20
        rot_range = 4.0
        shake_amp = 5
    
    # 选择主运动类型，但我们会组合多个
    motion_types = ['zoom_pan', 'zoom_rotate', 'pan_rotate', 'shake_zoom']
    main_motion = random.choice(motion_types)
    
    # 缩放因子（随时间变化）
    def scale_func(t):
        base_scale = 1.0
        scale_var = random.uniform(*scale_range) * (t / duration)
        # 加入正弦波产生呼吸效果
        breath = 0.02 * math.sin(t * 2.5)
        return base_scale + scale_var + breath
    
    # 平移位置（随时间变化，产生平滑移动）
    start_x = random.uniform(-pan_range, pan_range)
    end_x = random.uniform(-pan_range, pan_range)
    start_y = random.uniform(-pan_range*0.5, pan_range*0.5)
    end_y = random.uniform(-pan_range*0.5, pan_range*0.5)
    
    def pos_func(t):
        x = start_x + (end_x - start_x) * (t / duration)
        y = start_y + (end_y - start_y) * (t / duration)
        # 添加微小随机抖动
        jitter = 0.02 * math.sin(t * 10) * (1 - t/duration)  # 边缘抖动减弱
        return (x + jitter, y + jitter * 0.5)
    
    # 旋转角度（随时间缓慢变化）
    def rot_func(t):
        angle = random.uniform(-rot_range, rot_range) * (t / duration)
        # 加入微小的正弦波动
        angle += 0.5 * math.sin(t * 2)
        return angle
    
    # 应用组合变换
    try:
        # 先缩放
        clip = clip.resize(scale_func)
        # 再设置位置
        clip = clip.set_position(pos_func)
        # 最后旋转
        clip = clip.rotate(rot_func)
        
        # 如果场景是战斗或高潮，额外添加震动效果
        if scene_type in ["战斗", "高潮"]:
            def shake_effect(t):
                amp = shake_amp * (t / duration) * (1 - t / duration)  # 中间最大
                return (random.uniform(-amp, amp), random.uniform(-amp, amp))
            clip = clip.set_position(lambda t: (
                pos_func(t)[0] + shake_effect(t)[0],
                pos_func(t)[1] + shake_effect(t)[1]
            ))
        
        motion_desc = f"复合运动（缩放{scale_range[0]:.2f}-{scale_range[1]:.2f}，平移{pan_range:.2f}，旋转{rot_range:.1f}°）"
        return clip, motion_desc
    except Exception as e:
        print(f"⚠️ 运镜应用失败: {e}")
        return clip, "无运镜"

# ===================== 字幕 =====================
def add_subtitle(image_path, text, output_path):
    if not os.path.exists(image_path):
        return False
    try:
        img = Image.open(image_path).convert('RGB')
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("simhei.ttf", 50)
        except:
            font = ImageFont.load_default()
        
        max_width = IMAGE_SIZE[0] - 100
        lines = []
        current_line = ""
        for char in text:
            test_line = current_line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
        
        total_height = len(lines) * 70
        y = IMAGE_SIZE[1] - total_height - 100
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            x = (IMAGE_SIZE[0] - (bbox[2] - bbox[0])) // 2
            for dx, dy in [(-2, -2), (-2, 0), (-2, 2), (0, -2), (0, 2), (2, -2), (2, 0), (2, 2)]:
                draw.text((x+dx, y+dy), line, fill='black', font=font)
            draw.text((x, y), line, fill='white', font=font)
            y += 70
        
        img.save(output_path)
        return True
    except Exception as e:
        print(f"⚠️ 字幕添加失败: {e}")
        if os.path.exists(image_path):
            shutil.copy(image_path, output_path)
        return False

# ===================== 片头片尾 =====================
def create_header_footer():
    try:
        header = TextClip("⚠️ AI辅助制作", fontsize=60, color='white', font='SimHei',
                          stroke_color='black', stroke_width=2, size=(IMAGE_SIZE[0], 200))
        header = header.set_position(('center', 'top')).set_duration(3)
        header_bg = ColorClip(size=IMAGE_SIZE, color=(0,0,0), duration=3)
        header = CompositeVideoClip([header_bg, header])
        
        footer = TextClip("本剧由AI辅助生成，纯属娱乐", fontsize=50, color='white', font='SimHei',
                          stroke_color='black', stroke_width=2, size=(IMAGE_SIZE[0], 150))
        footer = footer.set_position(('center', 'center')).set_duration(5)
        footer_bg = ColorClip(size=IMAGE_SIZE, color=(0,0,0), duration=5)
        footer = CompositeVideoClip([footer_bg, footer])
        return header, footer
    except Exception as e:
        print(f"⚠️ 片头片尾创建失败: {e}")
        bg = ColorClip(size=IMAGE_SIZE, color=(0,0,0), duration=3)
        return bg, bg

# ===================== 视频合成 =====================
def compose(scenes, out_file):
    try:
        header, footer = create_header_footer()
        clips = [header]
        total = len(scenes)
        motion_log = []
        success_count = 0
        
        for i, s in enumerate(scenes):
            img_path = f"{OUTPUT_DIR}/img_{i}.jpg"
            if not os.path.exists(img_path):
                print(f"⚠️ 图片缺失: img_{i}.jpg，跳过")
                continue
            
            sub_path = f"{OUTPUT_DIR}/sub_{i}.jpg"
            subtitle_text = s.get('visual', '')[:15]
            if not add_subtitle(img_path, subtitle_text, sub_path):
                sub_path = img_path
            
            try:
                clip = ImageClip(sub_path).set_duration(SECONDS_PER_SCENE)
            except Exception as e:
                print(f"⚠️ 剪辑创建失败: {e}")
                continue
            
            scene_type = s.get('scene_type', '普通')
            clip, motion = apply_camera_motion(clip, SECONDS_PER_SCENE, scene_type)
            motion_log.append({"scene": i+1, "motion": motion, "type": scene_type})
            
            audio_path = f"{OUTPUT_DIR}/audio_{i}.mp3"
            if os.path.exists(audio_path):
                try:
                    audio_clip = AudioFileClip(audio_path)
                    if audio_clip.duration < SECONDS_PER_SCENE:
                        audio_clip = audio_loop(audio_clip, duration=SECONDS_PER_SCENE)
                    elif audio_clip.duration > SECONDS_PER_SCENE:
                        audio_clip = audio_clip.subclip(0, SECONDS_PER_SCENE)
                    clip = clip.set_audio(audio_clip)
                except Exception as e:
                    print(f"⚠️ 音频加载失败: {e}")
            
            clips.append(clip)
            success_count += 1
            if (i+1) % 5 == 0 or i == total-1:
                print(f"📹 合成进度: {i+1}/{total} (有效片段: {success_count})")
        
        clips.append(footer)
        if len(clips) <= 2:
            print("❌ 无有效片段，视频生成失败")
            return None, motion_log
        
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(out_file, fps=FPS, codec='libx264', 
                              audio_codec='aac', bitrate="3000k", preset="medium")
        print(f"✅ 视频生成: {out_file}")
        return final, motion_log
    except Exception as e:
        print(f"❌ 视频合成失败: {e}")
        return None, []

# ===================== 报告生成 =====================
def generate_report(ep_num, script, img_logs, audio_logs, motion_log, video_path, topic):
    try:
        report_dir = os.path.join(REPORT_BASE, f"第{ep_num:03d}集")
        os.makedirs(report_dir, exist_ok=True)
        success_images = sum(1 for log in img_logs if log.get('status') == 'success')
        failed_images = sum(1 for log in img_logs if log.get('status') == 'failed')
        placeholder_images = sum(1 for log in img_logs if log.get('status') == 'placeholder')
        success_audio = sum(1 for log in audio_logs if log.get('status') == 'success')
        
        with open(os.path.join(report_dir, "报告摘要.txt"), 'w', encoding='utf-8') as f:
            f.write(f"第{ep_num}集 创作报告\n")
            f.write(f"主题：{topic}\n")
            f.write(f"生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"总幕数：{len(script)}\n")
            f.write(f"图片：成功 {success_images}, 失败 {failed_images}, 占位 {placeholder_images}\n")
            f.write(f"配音：成功 {success_audio}/{len(audio_logs)}\n")
            if os.path.exists(video_path):
                f.write(f"视频大小：{round(os.path.getsize(video_path) / (1024*1024), 2)} MB\n")
        print(f"📄 报告已保存至：{report_dir}")
    except Exception as e:
        print(f"⚠️ 报告生成失败: {e}")

# ===================== 封面生成 =====================
def generate_cover(ep_num, title, output_path):
    try:
        bg = Image.new('RGB', IMAGE_SIZE, (30, 30, 80))
        draw = ImageDraw.Draw(bg)
        for i in range(5):
            x1 = random.randint(0, IMAGE_SIZE[0])
            y1 = random.randint(0, IMAGE_SIZE[1])
            x2 = random.randint(0, IMAGE_SIZE[0])
            y2 = random.randint(0, IMAGE_SIZE[1])
            draw.line((x1, y1, x2, y2), fill=(255, 200, 50), width=3)
        try:
            font = ImageFont.truetype("simhei.ttf", 150)
        except:
            font = ImageFont.load_default()
        lines = [title[i:i+6] for i in range(0, len(title), 6)]
        y = 200
        for line in lines[:4]:
            draw.text((IMAGE_SIZE[0]//2, y), line, fill=(255, 215, 0), font=font, anchor='mt')
            y += 180
        bg.save(output_path)
        print(f"📷 封面生成: {output_path}")
    except Exception as e:
        print(f"⚠️ 封面生成失败: {e}")

# ===================== 发布数据包 =====================
def generate_publish_package(episode_count, title, desc):
    package_dir = os.path.join(REPORT_BASE, "publish_package")
    os.makedirs(package_dir, exist_ok=True)
    with open(os.path.join(package_dir, "title.txt"), 'w', encoding='utf-8') as f:
        f.write(title)
    with open(os.path.join(package_dir, "description.txt"), 'w', encoding='utf-8') as f:
        f.write(desc[:200])
    cover_path = os.path.join(package_dir, "cover.jpg")
    generate_cover(episode_count, title, cover_path)
    print(f"📦 发布数据包已生成: {package_dir}")

# ===================== 制作单集 =====================
async def make_episode(ep_num, topic):
    print(f"\n{'='*60}")
    print(f"🎬 制作第 {ep_num} 集")
    print(f"📊 模式: 匿名 (免费，间隔{IMAGE_INTERVAL}s)")
    print(f"{'='*60}")
    
    state = load_state()
    gen = ScriptGen(state.get("last_ending", ""))
    script = gen.generate(topic)
    
    if ep_num == MAX_EPISODES:
        suffix = "，下季更精彩，敬请期待"
    else:
        suffix = "，未完待续"
    script[-1]['narration'] += suffix
    script[-1]['visual'] += suffix
    
    print(f"📝 剧本生成完成，共 {len(script)} 幕")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    img_logs = []
    print("\n🎨 开始生成图片...")
    for i, s in enumerate(script):
        print(f"📸 [{i+1}/{len(script)}] ", end="")
        prompt = s.get('prompt', s['visual'])
        log = generate_image(prompt, f"{OUTPUT_DIR}/img_{i}.jpg")
        img_logs.append(log)
        if i < len(script) - 1:
            print(f"⏳ 等待 {IMAGE_INTERVAL}s...")
            time.sleep(IMAGE_INTERVAL)
    
    audio_logs = []
    print("\n🎤 开始生成配音...")
    for i, s in enumerate(script):
        print(f"🎵 [{i+1}/{len(script)}] ", end="")
        log = await gen_audio(s['narration'], f"{OUTPUT_DIR}/audio_{i}.mp3")
        audio_logs.append(log)
        if i < len(script) - 1:
            await asyncio.sleep(AUDIO_INTERVAL)
    
    print("\n🎬 开始合成视频...")
    out_file = f"短剧_第{ep_num:03d}集_90s.mp4"
    final_video, motion_log = compose(script, out_file)
    
    if final_video is not None:
        generate_report(ep_num, script, img_logs, audio_logs, motion_log, out_file, topic)
    
    ending = script[-1]['narration']
    save_state(ep_num, ending)
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    print(f"\n✅ 第 {ep_num} 集完成！")
    
    env_file = os.environ.get('GITHUB_ENV')
    if env_file:
        with open(env_file, 'a') as f:
            f.write(f"EPISODE_NUM={ep_num}\n")
            f.write(f"VIDEO_FILE={out_file}\n")
    
    await asyncio.sleep(2)

# ===================== 主程序 =====================
async def main():
    print("=" * 60)
    print("🎬 AI短剧自动化工厂 v5.0（增强版）")
    print("=" * 60)
    print(f"📺 剧名：{DRAMA_TITLE}")
    print(f"🎯 总集数：{MAX_EPISODES}")
    print(f"👤 主角：{MAIN_CHARACTER['name']}")
    print(f"👥 配角：{', '.join(SIDE_CHARACTERS.keys())}")
    print(f"⏱️  图片间隔：{IMAGE_INTERVAL}s (避免限流)")
    print(f"⏱️  配音间隔：{AUDIO_INTERVAL}s")
    print(f"🔄 重试次数：{MAX_IMAGE_RETRIES}次")
    print(f"💰 费用：完全免费")
    print("=" * 60)
    
    create_silence()
    
    try:
        import PIL, moviepy, edge_tts, docx
        print("✅ 所有依赖库已安装")
    except ImportError as e:
        print(f"⚠️ 缺少依赖库: {e}")
        print("请运行: pip install pillow moviepy edge-tts python-docx requests")
        return
    
    topic = os.environ.get('TOPIC', '').strip()
    if not topic:
        topic = input("请输入主题（直接回车使用'修仙'）: ").strip() or "修仙"
    
    state = load_state()
    start = state.get("episode", 0) + 1
    
    if start > MAX_EPISODES:
        print("✅ 所有集数已完成！")
        return
    
    print(f"🚀 从第 {start} 集开始，共 {MAX_EPISODES} 集")
    print("⏰ 每集预计耗时：15-30分钟（取决于网络）")
    print("=" * 60)
    
    if start <= MAX_EPISODES:
        await make_episode(start, topic)
        if start == MAX_EPISODES:
            generate_publish_package(MAX_EPISODES, DRAMA_TITLE, DRAMA_DESC)
            print(f"\n🎉 全部 {MAX_EPISODES} 集生成完成！")
            print(f"📁 发布数据包在：{REPORT_BASE}/publish_package")
    else:
        print("✅ 所有集数已完成！")

if __name__ == "__main__":
    asyncio.run(main())
