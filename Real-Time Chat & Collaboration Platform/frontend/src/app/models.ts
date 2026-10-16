export interface ChatRoom {
  id: string;
  name: string;
  createdAt: string;
}

export interface ChatMessage {
  id: string;
  roomId: string;
  roomName: string;
  sender: string;
  content: string;
  createdAt: string;
}

export interface UserProfile {
  displayName: string;
  username: string;
  email: string;
}

export interface PresenceMember {
  sessionId: string;
  name: string;
  expiresAt: number;
  typingUntil: number;
}
