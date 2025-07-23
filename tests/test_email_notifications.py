import pytest
from app.core.email import should_send_email_notification
from app.schemas.enums import NotificationType


@pytest.mark.parametrize(
    "notification_type,user_preferences,expected_result",
    [
        # Test with globally enabled notifications
        (
            NotificationType.NEW_FOLLOWER,
            {"email_notifications": {"email_notifications_enabled": True, "email_new_follower": True}},
            True
        ),
        # Test with globally disabled notifications
        (
            NotificationType.NEW_FOLLOWER,
            {"email_notifications": {"email_notifications_enabled": False, "email_new_follower": True}},
            False
        ),
        # Test with specific notification type disabled
        (
            NotificationType.NEW_FOLLOWER,
            {"email_notifications": {"email_notifications_enabled": True, "email_new_follower": False}},
            False
        ),
        # Test with missing specific preference (should use default)
        (
            NotificationType.POST_COMMENT,
            {"email_notifications": {"email_notifications_enabled": True}},
            True  # Default for post_comment is True
        ),
        # Test with missing email_notifications section (should use defaults)
        (
            NotificationType.POST_REACTION,
            {},
            False  # Default for post_reaction is False
        ),
        # Test with empty preferences (should use defaults)
        (
            NotificationType.CONNECTION_REQUEST,
            {},
            True  # Default for connection_request is True
        ),
    ]
)
def test_should_send_email_notification(notification_type, user_preferences, expected_result):
    """Test the should_send_email_notification function with various user preferences"""
    result = should_send_email_notification(notification_type, user_preferences)
    assert result == expected_result


@pytest.mark.parametrize(
    "notification_type",
    [
        NotificationType.NEW_FOLLOWER,
        NotificationType.POST_COMMENT,
        NotificationType.POST_REACTION,
        NotificationType.CONNECTION_REQUEST,
        NotificationType.CONNECTION_ACCEPTED,
        NotificationType.NEW_MESSAGE,
        NotificationType.POST_TAG,
        NotificationType.BOOKMARK,
        NotificationType.JOB_APPLICATION,
        NotificationType.POST_REPOST,
    ]
)
def test_notification_type_mapping(notification_type):
    """Test that all notification types have a mapping in should_send_email_notification"""
    # This test ensures that all notification types are handled in the function
    # We just need to make sure it doesn't raise an exception
    result = should_send_email_notification(notification_type, {})
    # The result can be True or False depending on defaults, but it should be a boolean
    assert isinstance(result, bool)