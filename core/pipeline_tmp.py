            # 入库：status=accepted，chat_round=0 标记本轮新通过
            self.storage.mark_status(name, "accepted", chat_round=0, name=name)

            # 等对话框打开（雷电等模拟器跳转慢，之前 1-2 秒不够）
            input_rid = self.chatter._get_rid("buttons", "input_box")
            dialog_ready = False
            if input_rid:
                deadline = time.time() + 5.0
                while time.time() < deadline:
                    try:
                        el = self.driver.d(resourceId=input_rid)
                        if el.exists:
                            dialog_ready = True
                            break
                    except Exception:
                        pass
                    time.sleep(0.5)

            if not dialog_ready:
                self._logger.warning("Phase 1: 对话框未打开，跳过发消息 -> %s", name)
                self.greeter.go_back_to_chat_list()
                approved_count += 1
                if not self.greeter.enter_sayhi_list():
                    break
                time.sleep(0.8)
                continue

            # 发破冰消息（消息池第 1 池）
            if self._pool:
                icebreaker = self._pool.get_message_for_round(1)
                self._logger.info("Phase 1: 发送破冰消息 -> %s", name)
                ok = self.chatter.send_message(icebreaker)
                if not ok:
                    self._logger.warning("Phase 1: 破冰消息发送失败 -> %s", name)
                random_delay(self.settings)