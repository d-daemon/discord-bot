LANGUAGE_EMOJI_MAP = {
    'en': ['🇬🇧', '🇺🇸', '🇦🇺'],
    'es': ['🇪🇸', '🇲🇽', '🇦🇷', '🇨🇴'],
    'fr': ['🇫🇷', '🇧🇪'],
    'de': ['🇩🇪', '🇦🇹'],
    'it': ['🇮🇹'],
    'pt': ['🇵🇹', '🇧🇷'],
    'ru': ['🇷🇺'],
    'ja': ['🇯🇵'],
    'ko': ['🇰🇷'],
    'zh-CN': ['🇨🇳'],
    'zh-TW': ['🇹🇼', '🇭🇰'],
    'ar': ['🇸🇦', '🇪🇬', '🇦🇪'],
    'hi': ['🇮🇳'],
    'tr': ['🇹🇷'],
    'nl': ['🇳🇱'],
    'pl': ['🇵🇱'],
    'sv': ['🇸🇪'],
    'da': ['🇩🇰'],
    'fi': ['🇫🇮'],
    'no': ['🇳🇴'],
    'uk': ['🇺🇦'],
    'el': ['🇬🇷'],
    'he': ['🇮🇱'],
    'th': ['🇹🇭'],
    'vi': ['🇻🇳'],
    'id': ['🇮🇩'],
    'ms': ['🇲🇾'],
    'fa': ['🇮🇷'],
    'bn': ['🇧🇩'],
    'fil': ['🇵🇭'],
    'sw': ['🇰🇪', '🇹🇿'],
    'am': ['🇪🇹'],
    'ta': ['🇮🇳', '🇱🇰'],
    'te': ['🇮🇳'],
    'ur': ['🇵🇰', '🇮🇳'],
}

MULTI_LANG_COUNTRIES = {
    '🇨🇦': {'en': 'English', 'fr': 'French'},
    '🇨🇭': {'de': 'German', 'fr': 'French', 'it': 'Italian'},
    '🇧🇪': {'nl': 'Dutch', 'fr': 'French', 'de': 'German'},
}

LANG_CODE_MAP = {
    # Chinese variations
    'zh-cn': 'zh-CN',
    'zh-tw': 'zh-TW',
    'zh-hk': 'zh-TW',
    'zh': 'zh-CN',  # Default Chinese to Simplified
    'zhong': 'zh-CN',
    'chinese': 'zh-CN',
    'mandarin': 'zh-CN',

    # Hebrew
    'iw': 'he',
    'hebrew': 'he',

    # Javanese
    'jw': 'jv',
    'javanese': 'jv',

    # Filipino/Tagalog
    'tl': 'fil',
    'tagalog': 'fil',
    'filipino': 'fil',

    # Norwegian variations
    'no': 'nb',  # Default Norwegian to Bokmål
    'nor': 'nb',
    'norwegian': 'nb',

    # Greek
    'el': 'el',
    'greek': 'el',

    # Basque
    'eu': 'eu',
    'basque': 'eu',

    # Serbian variations
    'sr-latn': 'sr',  # Serbian Latin to Cyrillic
    'serbian': 'sr',

    # Azerbaijani
    'az': 'az',
    'azerbaijani': 'az',

    # Belarusian
    'be': 'be',
    'belarusian': 'be',

    # Bengali/Bangla
    'bn': 'bn',
    'bengali': 'bn',
    'bangla': 'bn',

    # Bosnian
    'bs': 'bs',
    'bosnian': 'bs',

    # Czech
    'cs': 'cs',
    'czech': 'cs',

    # Welsh
    'cy': 'cy',
    'welsh': 'cy',

    # Danish
    'da': 'da',
    'danish': 'da',

    # German
    'de': 'de',
    'german': 'de',

    # Estonian
    'et': 'et',
    'estonian': 'et',

    # Persian/Farsi
    'fa': 'fa',
    'persian': 'fa',
    'farsi': 'fa',

    # Finnish
    'fi': 'fi',
    'finnish': 'fi',

    # French
    'fr': 'fr',
    'french': 'fr',

    # Irish
    'ga': 'ga',
    'irish': 'ga',

    # Croatian
    'hr': 'hr',
    'croatian': 'hr',

    # Hungarian
    'hu': 'hu',
    'hungarian': 'hu',

    # Armenian
    'hy': 'hy',
    'armenian': 'hy',

    # Indonesian
    'id': 'id',
    'indonesian': 'id',

    # Icelandic
    'is': 'is',
    'icelandic': 'is',

    # Georgian
    'ka': 'ka',
    'georgian': 'ka',

    # Kazakh
    'kk': 'kk',
    'kazakh': 'kk',

    # Khmer
    'km': 'km',
    'khmer': 'km',

    # Korean
    'ko': 'ko',
    'korean': 'ko',

    # Kyrgyz
    'ky': 'ky',
    'kyrgyz': 'ky',

    # Lithuanian
    'lt': 'lt',
    'lithuanian': 'lt',

    # Latvian
    'lv': 'lv',
    'latvian': 'lv',

    # Macedonian
    'mk': 'mk',
    'macedonian': 'mk',

    # Mongolian
    'mn': 'mn',
    'mongolian': 'mn',

    # Malay
    'ms': 'ms',
    'malay': 'ms',

    # Burmese
    'my': 'my',
    'burmese': 'my',

    # Dutch
    'nl': 'nl',
    'dutch': 'nl',

    # Polish
    'pl': 'pl',
    'polish': 'pl',

    # Portuguese
    'pt': 'pt',
    'portuguese': 'pt',

    # Romanian
    'ro': 'ro',
    'romanian': 'ro',

    # Russian
    'ru': 'ru',
    'russian': 'ru',

    # Slovak
    'sk': 'sk',
    'slovak': 'sk',

    # Slovenian
    'sl': 'sl',
    'slovenian': 'sl',

    # Albanian
    'sq': 'sq',
    'albanian': 'sq',

    # Swedish
    'sv': 'sv',
    'swedish': 'sv',

    # Thai
    'th': 'th',
    'thai': 'th',

    # Turkish
    'tr': 'tr',
    'turkish': 'tr',

    # Ukrainian
    'uk': 'uk',
    'ukrainian': 'uk',

    # Urdu
    'ur': 'ur',
    'urdu': 'ur',

    # Uzbek
    'uz': 'uz',
    'uzbek': 'uz',

    # Vietnamese
    'vi': 'vi',
    'vietnamese': 'vi',

    # Yiddish
    'yi': 'yi',
    'yiddish': 'yi',

    # English
    'en': 'en',
    'english': 'en',
    'eng': 'en',

    # Spanish
    'es': 'es',
    'spanish': 'es',

    # Italian
    'it': 'it',
    'italian': 'it',

    # Japanese
    'ja': 'ja',
    'japanese': 'ja',

    # Arabic
    'ar': 'ar',
    'arabic': 'ar',

    # Hindi
    'hi': 'hi',
    'hindi': 'hi',

    # Swahili
    'sw': 'sw',
    'swahili': 'sw',

    # Tamil
    'ta': 'ta',
    'tamil': 'ta',

    # Telugu
    'te': 'te',
    'telugu': 'te',

    # Amharic
    'am': 'am',
    'amharic': 'am',

    # Maori
    'mi': 'mi',
    'maori': 'mi',

    # Nepali
    'ne': 'ne',
    'nepali': 'ne',

    # Sinhala
    'si': 'si',
    'sinhala': 'si',

    # Lao
    'lo': 'lo',
    'laotian': 'lo',

    # Haitian Creole
    'ht': 'ht',
    'haitian': 'ht',
    'haitian creole': 'ht',

    # Kurdish
    'ku': 'ku',
    'kurdish': 'ku',

    # Maltese
    'mt': 'mt',
    'maltese': 'mt',

    # Hmong
    'hmn': 'hmn',
    'hmong': 'hmn',

    # Xhosa
    'xh': 'xh',
    'xhosa': 'xh',

    # Zulu
    'zu': 'zu',
    'zulu': 'zu',

    # Afrikaans
    'af': 'af',
    'afrikaans': 'af',

    # Luxembourgish
    'lb': 'lb',
    'luxembourgish': 'lb',

    # Frisian
    'fy': 'fy',
    'frisian': 'fy',

    # Hausa
    'ha': 'ha',
    'hausa': 'ha',

    # Igbo
    'ig': 'ig',
    'igbo': 'ig',

    # Yoruba
    'yo': 'yo',
    'yoruba': 'yo',

    # Cebuano
    'ceb': 'ceb',
    'cebuano': 'ceb',

    # Sundanese
    'su': 'su',
    'sundanese': 'su',

    # Somali
    'so': 'so',
    'somali': 'so',

    # Pashto
    'ps': 'ps',
    'pashto': 'ps',

    # Chichewa
    'ny': 'ny',
    'chichewa': 'ny',
    'nyanja': 'ny',

    # Galician
    'gl': 'gl',
    'galician': 'gl',

    # Catalan
    'ca': 'ca',
    'catalan': 'ca',

    # Corsican
    'co': 'co',
    'corsican': 'co',

    # Esperanto
    'eo': 'eo',
    'esperanto': 'eo',

    # Hawaiian
    'haw': 'haw',
    'hawaiian': 'haw',

    # Samoan
    'sm': 'sm',
    'samoan': 'sm',

    # Scots Gaelic
    'gd': 'gd',
    'scots gaelic': 'gd',
    'scottish gaelic': 'gd',

    # Sesotho
    'st': 'st',
    'sesotho': 'st',
    'southern sotho': 'st',

    # Shona
    'sn': 'sn',
    'shona': 'sn',

    # Sindhi
    'sd': 'sd',
    'sindhi': 'sd',

    # Tajik
    'tg': 'tg',
    'tajik': 'tg',

    # Turkmen
    'tk': 'tk',
    'turkmen': 'tk',

    # Uyghur
    'ug': 'ug',
    'uyghur': 'ug',
}

# Generate emoji_to_lang mapping
EMOJI_TO_LANG = {emoji: lang for lang, emojis in LANGUAGE_EMOJI_MAP.items() for emoji in emojis}

# Add any additional language names or mappings here
ADDITIONAL_LANGUAGE_NAMES = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'zh-CN': 'Chinese (Simplified)',
    'zh-TW': 'Chinese (Traditional)',
    'ar': 'Arabic',
    'hi': 'Hindi',
    'tr': 'Turkish',
    'nl': 'Dutch',
    'pl': 'Polish',
    'sv': 'Swedish',
    'da': 'Danish',
    'fi': 'Finnish',
    'no': 'Norwegian',
    'uk': 'Ukrainian',
    'el': 'Greek',
    'he': 'Hebrew',
    'th': 'Thai',
    'vi': 'Vietnamese',
    'id': 'Indonesian',
    'ms': 'Malay',
    'fa': 'Persian',
    'bn': 'Bengali',
    'fil': 'Filipino',
    'sw': 'Swahili',
    'am': 'Amharic',
    'ta': 'Tamil',
    'te': 'Telugu',
    'ur': 'Urdu',
}