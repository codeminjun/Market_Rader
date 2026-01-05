"""
Discord Webhook 전송 모듈
"""
from typing import Optional
from discord_webhook import DiscordWebhook, DiscordEmbed

from config.settings import settings
from src.utils.logger import logger


class DiscordSender:
    """Discord Webhook 전송기"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.DISCORD_WEBHOOK_URL

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

        try:
            webhook = DiscordWebhook(
                url=self.webhook_url,
                content=content,
                username=username,
            )
            response = webhook.execute()

            if response.status_code in [200, 204]:
                logger.debug("Message sent successfully")
                return True
            else:
                logger.error(f"Failed to send message: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

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

        try:
            webhook = DiscordWebhook(
                url=self.webhook_url,
                username=username,
            )
            webhook.add_embed(embed)
            response = webhook.execute()

            if response.status_code in [200, 204]:
                logger.debug("Embed sent successfully")
                return True
            else:
                logger.error(f"Failed to send embed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending embed: {e}")
            return False

    def send_multiple_embeds(
        self,
        embeds: list[DiscordEmbed],
        username: str = "Market Rader",
        batch_size: int = 10,
    ) -> bool:
        """
        여러 Embed 전송 (Discord 제한: 메시지당 최대 10개)

        Args:
            embeds: DiscordEmbed 리스트
            username: 봇 이름
            batch_size: 배치 크기 (최대 10)

        Returns:
            전송 성공 여부
        """
        if not self.webhook_url:
            logger.error("Discord webhook URL not configured")
            return False

        batch_size = min(batch_size, 10)  # Discord 제한
        success = True

        for i in range(0, len(embeds), batch_size):
            batch = embeds[i:i + batch_size]

            try:
                webhook = DiscordWebhook(
                    url=self.webhook_url,
                    username=username,
                )

                for embed in batch:
                    webhook.add_embed(embed)

                response = webhook.execute()

                if response.status_code not in [200, 204]:
                    logger.error(f"Failed to send batch: {response.status_code}")
                    success = False

            except Exception as e:
                logger.error(f"Error sending batch: {e}")
                success = False

        return success


# 전역 인스턴스
discord_sender = DiscordSender()
