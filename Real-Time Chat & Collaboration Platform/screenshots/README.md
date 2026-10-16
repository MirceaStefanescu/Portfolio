# Verified demonstrations — Real-Time Chat & Collaboration Platform

Captured on 16 October 2026 from the local demonstration. No external paid service or real transaction was used.

UI images are direct browser captures. API and CLI images display the actual responses or verification output, with local paths abbreviated and credentials omitted. Reused execution evidence is explicitly dated in its image and was checked against unchanged source hashes. Expected rejection responses demonstrate validation and access control.

The evidence covers the existing demonstrated behavior; it does not certify arbitrary production workloads, provider accounts or external model quality. Original diagrams and earlier captures remain preserved.

| Function / observed behavior | Screenshot | Verification |
| --- | --- | --- |
| Local demonstration session | [action-session.png](action-session.png) | Frontend connects through the authenticated demo WebSocket |
| Create and select room | [action-create-room.png](action-create-room.png) | New room is selected |
| Presence and typing indicators | [action-presence-typing.png](action-presence-typing.png) | Second browser receives presence and typing from first |
| Real-time message delivery | [action-receive-message.png](action-receive-message.png) | First browser message is delivered to second browser |
| Bidirectional conversation | [action-bidirectional.png](action-bidirectional.png) | Both independently connected browsers exchange messages |
| Search message history | [action-search.png](action-search.png) | Search returns only matching message |
| Clear search | [action-clear-search.png](action-clear-search.png) | Full conversation is restored |
| Persistent room history | [action-history-persistence.png](action-history-persistence.png) | Reload retrieves both messages from persistent storage |
| Responsive chat | [action-mobile.png](action-mobile.png) | No horizontal overflow at 390px |
| Integrated persistence, validation and recovery checks | [action-chat-integration.png](action-chat-integration.png) | Successful current execution of scripts/demo-check.py chat; local services and synthetic data only. |
