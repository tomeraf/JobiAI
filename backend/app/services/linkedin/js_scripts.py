"""
JavaScript scripts for LinkedIn page evaluation.

Centralized JavaScript code that gets executed in the browser context.
"""

# System messages to filter out when checking message history
SYSTEM_MESSAGE_PATTERNS = [
    'accepted your invitation',
    'you are now connected',
    'sent you a connection request',
    'wants to connect',
    'connection request',
    'this message has been deleted',
]


def _get_shadow_dom_helper_start() -> str:
    """
    Start of IIFE wrapper with shadow DOM helper functions.
    LinkedIn 2026 uses shadow DOM for messaging UI.
    """
    return """
        (() => {
            const findInShadowDOM = (selector) => {
                // Try light DOM first
                let result = document.querySelector(selector);
                if (result) return result;

                // Search in shadow roots
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.shadowRoot) {
                        result = el.shadowRoot.querySelector(selector);
                        if (result) return result;
                    }
                }
                return null;
            };

            const findAllInShadowDOM = (selector) => {
                const results = [];

                // Add from light DOM
                document.querySelectorAll(selector).forEach(el => results.push(el));

                // Add from shadow roots
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.shadowRoot) {
                        el.shadowRoot.querySelectorAll(selector).forEach(shadowEl => results.push(shadowEl));
                    }
                }
                return results;
            };
    """


def _get_shadow_dom_helper_end() -> str:
    """End of IIFE wrapper."""
    return """
        })()
    """


def get_message_history_script() -> str:
    """
    JavaScript to check for message history in a chat modal.

    Returns a dict with:
        - count: Number of real messages (excluding system messages)
        - texts: Preview of detected messages
        - method: Detection method used
        - debug: Debug information
    """
    return _get_shadow_dom_helper_start() + """
            const result = { count: 0, texts: [], method: '', debug: {} };

            // Find the chat dialog (check shadow DOM too - LinkedIn 2026)
            const roleDialog = findInShadowDOM('[role="dialog"]');
            const overlayBubble = findInShadowDOM('.msg-overlay-conversation-bubble');
            result.debug.hasRoleDialog = !!roleDialog;
            result.debug.hasOverlayBubble = !!overlayBubble;

            const dialog = roleDialog || overlayBubble;
            if (!dialog) {
                result.count = -1;
                result.method = 'no dialog';
                return result;
            }

            // Debug info
            result.debug.msgBodiesCount = dialog.querySelectorAll('.msg-s-event-listitem__body').length;
            result.debug.msgBubblesCount = dialog.querySelectorAll('.msg-s-message-group__bubble').length;

            // System message patterns to filter
            const systemPatterns = [
                'accepted your invitation',
                'you are now connected',
                'sent you a connection request',
                'wants to connect',
                'connection request',
                'this message has been deleted'
            ];

            const isSystemMessage = (text) => {
                const textLower = text.toLowerCase();
                return systemPatterns.some(pattern => textLower.includes(pattern));
            };

            // Primary method: Look for message body elements
            const messageBodies = dialog.querySelectorAll('.msg-s-event-listitem__body');
            if (messageBodies.length > 0) {
                result.method = 'bodies';
                messageBodies.forEach(body => {
                    const text = body.textContent.trim();
                    if (isSystemMessage(text)) {
                        result.texts.push('[SYSTEM] ' + text.substring(0, 50));
                        return;
                    }
                    result.count++;
                    result.texts.push(text.substring(0, 50));
                });
                return result;
            }

            // Fallback: Look for message bubbles
            const messageBubbles = dialog.querySelectorAll('.msg-s-message-group__bubble');
            if (messageBubbles.length > 0) {
                result.method = 'bubbles';
                messageBubbles.forEach(bubble => {
                    const text = bubble.textContent.trim();
                    if (isSystemMessage(text)) {
                        result.texts.push('[SYSTEM] ' + text.substring(0, 50));
                        return;
                    }
                    result.count++;
                    result.texts.push(text.substring(0, 50));
                });
                return result;
            }

            // Fallback: Look for message list
            const messageList = dialog.querySelector('ul.msg-s-message-list-content') ||
                               dialog.querySelector('ul.msg-s-message-list');
            if (!messageList) {
                result.count = -2;
                result.method = 'no list';
                return result;
            }

            result.method = 'events';
            const messageEvents = messageList.querySelectorAll('li.msg-s-message-list__event');
            messageEvents.forEach(event => {
                const messageBody = event.querySelector('.msg-s-event-listitem__body');
                if (messageBody) {
                    const text = messageBody.textContent.trim();
                    if (isSystemMessage(text)) {
                        result.texts.push('[SYSTEM] ' + text.substring(0, 50));
                        return;
                    }
                    result.count++;
                    result.texts.push(text.substring(0, 50));
                }
            });

            return result;
    """ + _get_shadow_dom_helper_end()


def get_reply_check_script(contact_name: str) -> str:
    """
    JavaScript to check for replies from a contact in an open conversation.

    Takes contactName as parameter and returns:
        - found: Whether the conversation was found
        - hasReply: Whether they've replied
        - inboundCount: Number of messages from them
        - outboundCount: Number of messages from us
        - debug: Debug information
    """
    # Escape any quotes in contact name
    escaped_name = contact_name.replace("'", "\\'").replace('"', '\\"')
    return _get_shadow_dom_helper_start() + '''
            const contactName = "''' + escaped_name + '''";
            const bubbleSelectors = [
                '.msg-overlay-conversation-bubble',
                '.msg-convo-wrapper',
                '.msg-s-message-list',
                '.msg-s-message-list-container',
                '[role="dialog"]'
            ];

            let bubble = null;
            for (const sel of bubbleSelectors) {
                bubble = findInShadowDOM(sel);
                if (bubble) break;
            }

            if (!bubble) {
                return { found: false, error: 'No conversation bubble found' };
            }

            // Find message items
            let messageItems = bubble.querySelectorAll('.msg-s-message-list__event');
            if (messageItems.length === 0) {
                messageItems = bubble.querySelectorAll('.msg-s-message-group');
            }

            if (messageItems.length === 0) {
                return { found: false, error: 'No message items found' };
            }

            const contactFirstName = contactName.split(' ')[0].toLowerCase();

            let inboundCount = 0;
            let outboundCount = 0;
            let debugInfo = [];

            for (const item of messageItems) {
                const classes = item.className.toLowerCase();
                let isInbound = false;
                let detectionMethod = 'default_outbound';

                // Check explicit CSS classes
                if (classes.includes('outbound')) {
                    isInbound = false;
                    detectionMethod = 'outbound_class';
                } else if (classes.includes('inbound')) {
                    isInbound = true;
                    detectionMethod = 'inbound_class';
                }

                // Look for their avatar
                if (!isInbound) {
                    const avatarSelectors = [
                        '.msg-s-message-group__profile-image',
                        '.presence-entity__image',
                        'img[class*="profile"]'
                    ];
                    for (const sel of avatarSelectors) {
                        const avatar = item.querySelector(sel);
                        if (avatar) {
                            const avatarAlt = (avatar.alt || '').toLowerCase();
                            if (avatarAlt && avatarAlt.includes(contactFirstName)) {
                                isInbound = true;
                                detectionMethod = 'avatar_contains_name';
                                break;
                            }
                        }
                    }
                }

                // Check sender name
                if (!isInbound) {
                    const senderSelectors = [
                        '.msg-s-message-group__name',
                        '.msg-s-event-listitem__name'
                    ];
                    for (const sel of senderSelectors) {
                        const senderEl = item.querySelector(sel);
                        if (senderEl) {
                            const senderText = senderEl.textContent.toLowerCase().trim();
                            if (senderText && senderText.includes(contactFirstName)) {
                                isInbound = true;
                                detectionMethod = 'sender_name_match';
                                break;
                            }
                        }
                    }
                }

                if (isInbound) {
                    inboundCount++;
                } else {
                    outboundCount++;
                }

                debugInfo.push({
                    isInbound: isInbound,
                    method: detectionMethod,
                    textPreview: (item.textContent || '').substring(0, 50)
                });
            }

            return {
                found: true,
                totalMessages: messageItems.length,
                inboundCount: inboundCount,
                outboundCount: outboundCount,
                hasReply: inboundCount > 0,
                contactFirstName: contactFirstName,
                debug: debugInfo
            };
    ''' + _get_shadow_dom_helper_end()


def get_close_overlay_script() -> str:
    """JavaScript to close all message overlays."""
    return _get_shadow_dom_helper_start() + """
            let closedCount = 0;

            // Search in both light DOM and shadow DOM
            const closeButtonsByAria = findAllInShadowDOM(
                'button[aria-label*="Close"]'
            );
            closeButtonsByAria.forEach(btn => {
                try { btn.click(); closedCount++; } catch (e) {}
            });

            if (closedCount === 0) {
                const conversationBubbles = findAllInShadowDOM('.msg-overlay-conversation-bubble');
                conversationBubbles.forEach(bubble => {
                    const closeBtn = bubble.querySelector(
                        '.msg-overlay-bubble-header__control:not(.msg-overlay-conversation-bubble__expand-btn)'
                    );
                    if (closeBtn) {
                        try { closeBtn.click(); closedCount++; } catch (e) {}
                    }
                });
            }

            const draftCloseButtons = findAllInShadowDOM(
                'button[aria-label="Close your draft conversation"]'
            );
            draftCloseButtons.forEach(btn => {
                try { btn.click(); closedCount++; } catch (e) {}
            });

            if (closedCount === 0) {
                document.dispatchEvent(new KeyboardEvent('keydown', {
                    key: 'Escape', code: 'Escape', keyCode: 27, bubbles: true
                }));
            }

            return closedCount;
    """ + _get_shadow_dom_helper_end()


def get_close_current_chat_script() -> str:
    """JavaScript to close the current chat modal."""
    return _get_shadow_dom_helper_start() + """
            const closeButtons = findAllInShadowDOM('button[aria-label*="Close"]');
            for (const btn of closeButtons) {
                try { btn.click(); break; } catch (e) {}
            }
    """ + _get_shadow_dom_helper_end()


def get_check_overlay_open_script() -> str:
    """JavaScript to check if any overlay is open."""
    return _get_shadow_dom_helper_start() + """
            return !!findInShadowDOM('.msg-overlay-conversation-bubble') || !!findInShadowDOM('[role="dialog"]');
    """ + _get_shadow_dom_helper_end()


def get_scroll_to_bottom_script() -> str:
    """JavaScript to scroll to the bottom of the page."""
    return "window.scrollTo(0, document.body.scrollHeight)"
