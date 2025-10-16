import { Component, OnInit } from '@angular/core';
import { ChatService } from './services/chat.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent implements OnInit {
  title = 'AI Business Assistant';
  messages: any[] = [];
  newMessage = '';
  isConnected = false;
  clientId = 'demo-client-' + Math.random().toString(36).substr(2, 9);

  constructor(private chatService: ChatService) {}

  ngOnInit() {
    this.connectToChat();
  }

  connectToChat() {
    this.chatService.connect(this.clientId);
    
    this.chatService.getConnectionStatus().subscribe(status => {
      this.isConnected = status;
      if (status) {
        this.messages.push({
          type: 'system',
          content: 'Connected to AI Assistant',
          timestamp: new Date()
        });
      }
    });

    this.chatService.getMessages().subscribe(message => {
      this.messages.push({
        ...message,
        timestamp: new Date()
      });
    });
  }

  sendMessage() {
    if (this.newMessage.trim()) {
      // Add user message to UI
      this.messages.push({
        type: 'user',
        content: this.newMessage,
        timestamp: new Date()
      });

      // Send to backend
      this.chatService.sendMessage(this.newMessage);
      this.newMessage = '';
    }
  }

  getMessageClass(message: any): string {
    if (message.type === 'user') return 'user-message';
    if (message.type === 'system') return 'system-message';
    return 'assistant-message';
  }
}