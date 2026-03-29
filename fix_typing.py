import glob
import re

files_to_update = [
    'bot/handlers/weight_handler.py',
    'bot/handlers/skin.py',
    'bot/handlers/chat_handler.py',
    'bot/handlers/medi.py'
]

for filepath in files_to_update:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        old_content = content
        
        # Replace the string literal with the Enum
        if '"typing"' in content:
            content = content.replace('send_chat_action(telegram_id, "typing")', 'send_chat_action(telegram_id, ChatAction.TYPING)')
            
        # Ensure ChatAction is imported
        if 'ChatAction' in content and 'import ChatAction' not in content:
            if 'from pyrogram.enums import ParseMode' in content:
                content = content.replace('from pyrogram.enums import ParseMode', 'from pyrogram.enums import ParseMode, ChatAction')
            elif 'from pyrogram.enums import' in content:
                content = re.sub(r'(from pyrogram\.enums import [^\n]+)', r'\1, ChatAction', content, count=1)
            else:
                # Top level import insertion
                lines = content.split('\n')
                lines.insert(0, 'from pyrogram.enums import ChatAction')
                content = '\n'.join(lines)
                
        if content != old_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {filepath}")
            
    except Exception as e:
        print(f"Failed to process {filepath}: {e}")
