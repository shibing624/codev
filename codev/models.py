# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description:
"""
import os
from typing import List, Optional
from loguru import logger
from openai import OpenAI

from codev.config import OPENAI_BASE_URL


def get_available_models() -> List[str]:
    """
    Get a list of available models from the OpenAI API
    
    Returns:
        List of model names that can be used with the API
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning(f"OPENAI_API_KEY environment variable not set, api_key: {api_key}")
        return []

    try:
        # Create OpenAI client
        client = OpenAI(
            api_key=api_key,
            base_url=OPENAI_BASE_URL
        )

        # Fetch models
        response = client.models.list()
        models = []

        # Extract model IDs
        for model in response.data:
            models.append(model.id)
        gpt_models = [m for m in models if m]
        return gpt_models
    except Exception as e:
        logger.error(f"Error fetching models: {str(e)}")
        return []
