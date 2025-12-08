"""
Dictionary Service - ดึงคำศัพท์จาก Backend API
สำหรับใช้สร้าง initial_prompt ให้กับ Whisper
"""

import logging
import os
import aiohttp
import asyncio
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class DictionaryService:
    """
    Service สำหรับดึงคำศัพท์จาก Backend Dictionary API
    """
    
    def __init__(self):
        # Backend API Base URL จาก environment variable
        self.backend_base_url = os.getenv(
            'BACKEND_API_BASE_URL',
            os.getenv('BACKEND_URL', 'http://localhost:5173')
        ).rstrip('/')
        
        # API Endpoint
        self.dictionary_endpoint = '/api/word-management/dictionary'
        
        # Timeout สำหรับ API calls
        self.timeout = aiohttp.ClientTimeout(total=5.0)  # 5 seconds timeout
        
        logger.info(f"📚 DictionaryService initialized with Backend URL: {self.backend_base_url}")
    
    async def fetch_dictionary_words(
        self,
        user_id: Optional[str] = None,
        scope: str = "Global",
        language: str = "thai",
        limit: int = 500
    ) -> List[str]:
        """
        ดึงคำศัพท์จาก Backend Dictionary API
        
        Args:
            user_id: User ID (สำหรับ Personal scope)
            scope: "Global" หรือ "Personal" (default: "Global")
            language: ภาษา (default: "thai")
            limit: จำนวนคำสูงสุด (default: 500)
        
        Returns:
            List[str]: รายการคำศัพท์
        
        Example:
            words = await dictionary_service.fetch_dictionary_words(
                user_id="123",
                scope="Global",
                language="thai"
            )
        """
        try:
            # สร้าง URL
            url = urljoin(self.backend_base_url, self.dictionary_endpoint)
            
            # Parameters
            params = {
                "language": language,
                "limit": limit,
                "includeGlobal": True,  # รวม Global words ด้วย
            }
            
            # เพิ่ม user_id ถ้ามี (สำหรับ Personal scope)
            if user_id:
                params["ownerUserId"] = user_id
            
            # เรียก API
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Parse response (รองรับหลายรูปแบบ)
                        items = []
                        if isinstance(data, dict):
                            items = data.get('data', data.get('Data', []))
                        elif isinstance(data, list):
                            items = data
                        
                        # Extract words
                        words = []
                        for item in items:
                            if isinstance(item, dict):
                                word = item.get('word') or item.get('Word')
                                if word and isinstance(word, str):
                                    words.append(word.strip())
                            elif isinstance(item, str):
                                words.append(item.strip())
                        
                        # Filter by scope (ถ้า API รองรับ)
                        # Note: API อาจจะ filter ให้แล้ว แต่วาง filter เพิ่มเติมเพื่อความแน่นอน
                        if scope == "Personal" and user_id:
                            # ถ้าเป็น Personal scope, เอาเฉพาะ words ที่มี ownerUserId ตรงกัน
                            filtered_words = []
                            for item in items:
                                if isinstance(item, dict):
                                    owner_user_id = item.get('ownerUserId') or item.get('OwnerUserId')
                                    if owner_user_id == user_id:
                                        word = item.get('word') or item.get('Word')
                                        if word:
                                            filtered_words.append(word.strip())
                            words = filtered_words if filtered_words else words
                        
                        logger.info(
                            f"📚 Fetched {len(words)} dictionary words from Backend "
                            f"(scope={scope}, language={language}, user_id={user_id or 'None'})"
                        )
                        
                        return words[:limit]  # จำกัดจำนวนคำ
                    else:
                        error_text = await response.text()
                        logger.warning(
                            f"⚠️ Backend Dictionary API returned {response.status}: {error_text[:200]}"
                        )
                        return []
                        
        except aiohttp.ClientError as e:
            logger.warning(f"⚠️ Failed to fetch dictionary from Backend API: {e}")
            return []
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Backend Dictionary API timeout (>{self.timeout.total}s)")
            return []
        except Exception as e:
            logger.error(f"❌ Error fetching dictionary words: {e}", exc_info=True)
            return []
    
    async def fetch_global_words(self, language: str = "thai", limit: int = 500) -> List[str]:
        """
        ดึงคำศัพท์ Global scope เท่านั้น
        
        Args:
            language: ภาษา (default: "thai")
            limit: จำนวนคำสูงสุด (default: 500)
        
        Returns:
            List[str]: รายการคำศัพท์ Global
        """
        return await self.fetch_dictionary_words(
            user_id=None,
            scope="Global",
            language=language,
            limit=limit
        )
    
    async def fetch_user_words(
        self,
        user_id: str,
        language: str = "thai",
        limit: int = 500
    ) -> List[str]:
        """
        ดึงคำศัพท์ Personal scope ของ user
        
        Args:
            user_id: User ID
            language: ภาษา (default: "thai")
            limit: จำนวนคำสูงสุด (default: 500)
        
        Returns:
            List[str]: รายการคำศัพท์ Personal
        """
        return await self.fetch_dictionary_words(
            user_id=user_id,
            scope="Personal",
            language=language,
            limit=limit
        )
    
    async def fetch_combined_words(
        self,
        user_id: Optional[str] = None,
        language: str = "thai",
        global_limit: int = 300,
        personal_limit: int = 200
    ) -> List[str]:
        """
        ดึงคำศัพท์ทั้ง Global และ Personal (ถ้ามี user_id)
        
        Args:
            user_id: User ID (optional)
            language: ภาษา (default: "thai")
            global_limit: จำนวนคำ Global (default: 300)
            personal_limit: จำนวนคำ Personal (default: 200)
        
        Returns:
            List[str]: รายการคำศัพท์รวม (Global + Personal)
        """
        words = []
        
        # ดึง Global words
        global_words = await self.fetch_global_words(language=language, limit=global_limit)
        words.extend(global_words)
        
        # ดึง Personal words (ถ้ามี user_id)
        if user_id:
            personal_words = await self.fetch_user_words(
                user_id=user_id,
                language=language,
                limit=personal_limit
            )
            words.extend(personal_words)
        
        # Deduplicate และ return
        return list(dict.fromkeys(words))  # ใช้ dict.fromkeys() เพื่อคงลำดับ

