// ============================================================
// 密钥池管理
// ============================================================

import fs from 'fs';
import path from 'path';
import { config } from './config.js';
import { logger } from './logger.js';
import { KeyInfo } from './types.js';

export class KeyManager {
  private keys: KeyInfo[] = [];
  private currentIndex = 0;
  private cooldownKeys: Map<string, Date> = new Map();
  
  constructor() {
    this.loadKeys();
    // 每5分钟重新加载密钥
    setInterval(() => this.loadKeys(), 5 * 60 * 1000);
  }
  
  /**
   * 从文件加载密钥
   */
  loadKeys(): void {
    try {
      const keysPath = path.join(config.keysDir, config.keysFile);
      
      if (!fs.existsSync(keysPath)) {
        logger.warn(`密钥文件不存在: ${keysPath}`);
        return;
      }
      
      const content = fs.readFileSync(keysPath, 'utf-8');
      const lines = content.split('\n').filter(line => line.trim());
      
      this.keys = lines.map(key => ({
        key: key.trim(),
        provider: 'openai' as const, // Vercel AI Gateway 使用统一密钥
        failCount: 0,
      }));
      
      logger.info(`从 ${config.keysFile} 加载了 ${this.keys.length} 个密钥`);
    } catch (error) {
      logger.error(`加载密钥失败: ${error}`);
    }
  }
  
  /**
   * 获取下一个可用密钥
   */
  getNextKey(): string | null {
    const now = new Date();
    const availableKeys = this.keys.filter(k => {
      const cooldownUntil = this.cooldownKeys.get(k.key);
      return !cooldownUntil || cooldownUntil <= now;
    });
    
    if (availableKeys.length === 0) {
      logger.error('没有可用的密钥');
      return null;
    }
    
    // 轮询选择密钥
    this.currentIndex = (this.currentIndex + 1) % availableKeys.length;
    const selected = availableKeys[this.currentIndex];
    
    return selected.key;
  }
  
  /**
   * 标记密钥失败
   */
  markKeyFailed(key: string): void {
    const keyInfo = this.keys.find(k => k.key === key);
    if (keyInfo) {
      keyInfo.failCount++;
      
      // 失败次数过多，进入冷却
      if (keyInfo.failCount >= 3) {
        const cooldownUntil = new Date();
        cooldownUntil.setHours(cooldownUntil.getHours() + config.cooldownHours);
        this.cooldownKeys.set(key, cooldownUntil);
        keyInfo.failCount = 0;
        
        logger.warn(`密钥 ${key.substring(0, 8)}**** 进入冷却，直到 ${cooldownUntil.toISOString()}`);
      }
    }
  }
  
  /**
   * 标记密钥成功
   */
  markKeySuccess(key: string): void {
    const keyInfo = this.keys.find(k => k.key === key);
    if (keyInfo) {
      keyInfo.failCount = 0;
      keyInfo.lastUsed = new Date();
    }
  }
  
  /**
   * 获取密钥统计信息
   */
  getStats(): { total: number; available: number; inCooldown: number } {
    const now = new Date();
    const inCooldown = Array.from(this.cooldownKeys.values()).filter(d => d > now).length;
    
    return {
      total: this.keys.length,
      available: this.keys.length - inCooldown,
      inCooldown,
    };
  }
}

export const keyManager = new KeyManager();
