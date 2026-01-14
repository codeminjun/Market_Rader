"""
Discord Webhook 전송 모듈
"""
import time
from typing import Optional
from discord_webhook import DiscordWebhook, DiscordEmbed

from config.settings import settings
from src.utils.logger import logger


class RetryConfig:
    """재시도 설정"""
    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # 초
    MAX_DELAY = 10.0  # 초
    RATE_LIMIT_DELAY = 0.3  # 초 (Discord 기본 제한은 5 req/s)


class DiscordSender:
    """Discord Webhook 전송기 (재시도 로직 포함)"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.DISCORD_WEBHOOK_URL

    def _retry_with_backoff(
        self,
        operation: callable,
        max_retries: int = RetryConfig.MAX_RETRIES,
    ) -> tuple[bool, any]:
        """
        지수 백오프를 사용한 재시도 로직

        Args:
            operation: 실행할 함수
            max_retries: 최대 재시도 횟수

        Returns:
            (성공 여부, 응답 또는 예외)
        """
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                response = operation()

                if response.status_code in [200, 204]:
                    return True, response

                # Rate limit (429) 처리
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", RetryConfig.BASE_DELAY))
                    logger.warning(f"Rate limited, waiting {retry_after}s (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(min(retry_after, RetryConfig.MAX_DELAY))
                    continue

                # 5xx 서버 에러는 재시도
                if 500 <= response.status_code < 600:
                    delay = min(RetryConfig.BASE_DELAY * (2 ** attempt), RetryConfig.MAX_DELAY)
                    logger.warning(f"Server error {response.status_code}, retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(delay)
                    continue

                # 다른 에러는 재시도하지 않음
                logger.error(f"Request failed with status {response.status_code}")
                return False, response

            except Exception as e:
                last_exception = e
                delay = min(RetryConfig.BASE_DELAY * (2 ** attempt), RetryConfig.MAX_DELAY)
                logger.warning(f"Request exception: {e}, retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1})")
                time.sleep(delay)

        logger.error(f"All {max_retries + 1} attempts failed. Last error: {last_exception}")
        return False, last_exception

    def send_message(
        self,
        content: str,
        username: str = "Market Rader",
    ) -> bool:
        """
        간단한 텍스트 메시지 전송

        Args:
            content: 메시지 내용
            username: 봇 이름

        Returns:
            전송 성공 여부
        """
        if not self.webhook_url:
            logger.error("Discord webhook URL not configured")
            return False

        def _execute():
            webhook = DiscordWebhook(
                url=self.webhook_url,
                content=content,
                username=username,
            )
            return webhook.execute()

        success, _ = self._retry_with_backoff(_execute)
        if success:
            logger.debug("Message sent successfully")
        return success

    def send_embed(
        self,
        embed: DiscordEmbed,
        username: str = "Market Rader",
    ) -> bool:
        """
        Embed 전송

        Args:
            embed: DiscordEmbed 객체
            username: 봇 이름

        Returns:
            전송 성공 여부
        """
        if not self.webhook_url:
            logger.error("Discord webhook URL not configured")
            return False

        def _execute():
            webhook = DiscordWebhook(
                url=self.webhook_url,
                username=username,
            )
            webhook.add_embed(embed)
            return webhook.execute()

        success, _ = self._retry_with_backoff(_execute)
        if success:
            logger.debug("Embed sent successfully")
        return success

    def send_multiple_embeds(
        self,
        embeds: list[DiscordEmbed],
        username: str = "Market Rader",
        batch_size: int = 5,
    ) -> bool:
        """
        여러 Embed 전송 (Discord 제한: 총 6000자, 메시지당 최대 10개)

        Args:
            embeds: DiscordEmbed 리스트
            username: 봇 이름
            batch_size: 배치 크기 (6000자 제한 대응, 기본값 5로 증가)

        Returns:
            전송 성공 여부
        """
        if not self.webhook_url:
            logger.error("Discord webhook URL not configured")
            return False

        batch_size = min(batch_size, 10)  # Discord 제한
        success = True
        failed_batches = 0
        total_batches = (len(embeds) + batch_size - 1) // batch_size

        for i in range(0, len(embeds), batch_size):
            batch = embeds[i:i + batch_size]

            def _execute_batch():
                webhook = DiscordWebhook(
                    url=self.webhook_url,
                    username=username,
                )
                for embed in batch:
                    webhook.add_embed(embed)
                return webhook.execute()

            batch_success, _ = self._retry_with_backoff(_execute_batch)

            if not batch_success:
                logger.error(f"Failed to send batch {i // batch_size + 1}/{total_batches}")
                success = False
                failed_batches += 1
            else:
                logger.debug(f"Batch {i // batch_size + 1}/{total_batches} sent successfully")

            # Rate limit 방지 (마지막 배치 제외)
            if i + batch_size < len(embeds):
                time.sleep(RetryConfig.RATE_LIMIT_DELAY)

        if failed_batches > 0:
            logger.warning(f"{failed_batches} batch(es) failed out of {total_batches}")

        return success


# 전역 인스턴스
discord_sender = DiscordSender()
