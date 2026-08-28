C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\engine>python -c "from pathlib import Path; lines=Path('bot.py').read_text(encoding='utf-8').splitlines(); print('\n'.join(f'{i+1}: {lines[i]}' for i in range(214,625)))"
215:
216:     # ========================================================
217:     # TELEGRAM API NETWORK CONTROL V2
218:     #
219:     # Обычные API-запросы:
220:     #   TCP/TLS/HTTP timeout = 5 секунд
221:     #   максимум 2 попытки
222:     #   пауза между попытками = 0.5 сек.
223:     #
224:     # getUpdates:
225:     #   используется длинный POLL_TIMEOUT.
226:     #
227:     # Важно:
228:     #   timeout устанавливается не только на TCP connect,
229:     #   но и на уже созданные TCP/TLS sockets.
230:     #
231:     # Поэтому зависший TLS/HTTP recv() также не может
232:     # блокировать бота бесконечно.
233:     # ========================================================
234:
235:     if params is None:
236:         params = {}
237:
238:     path = f"/bot{BOT_TOKEN}/{method}"
239:
240:     if params:
241:         query = urlencode(
242:             params,
243:             encoding="utf-8"
244:         )
245:
246:         path += "?" + query
247:
248:     if method == "getUpdates":
249:         telegram_api_retries = 3
250:         telegram_api_retry_delay = 3
251:         telegram_api_timeout = POLL_TIMEOUT + 10
252:
253:     else:
254:         telegram_api_retries = 2
255:         telegram_api_retry_delay = 0.5
256:         telegram_api_timeout = 5
257:
258:     last_error = None
259:
260:     for attempt in range(
261:         1,
262:         telegram_api_retries + 1
263:     ):
264:
265:         sock = None
266:         tls_sock = None
267:
268:         try:
269:
270:             if attempt > 1:
271:
272:                 print(
273:                     "Telegram API: повтор запроса "
274:                     f"{attempt}/{telegram_api_retries} "
275:                     f"через {telegram_api_retry_delay} сек."
276:                 )
277:
278:                 time.sleep(
279:                     telegram_api_retry_delay
280:                 )
281:
282:             print(
283:                 "Telegram API: TCP connection "
284:                 f"attempt {attempt}/{telegram_api_retries}..."
285:             )
286:
287:             # ------------------------------------------------
288:             # TCP CONNECT
289:             # ------------------------------------------------
290:
291:             try:
292:
293:                 sock = socket.create_connection(
294:                     (
295:                         TELEGRAM_IP,
296:                         TELEGRAM_PORT
297:                     ),
298:                     timeout=telegram_api_timeout
299:                 )
300:
301:                 # Важно:
302:                 # timeout сохраняется и после установления TCP.
303:                 sock.settimeout(
304:                     telegram_api_timeout
305:                 )
306:
307:                 print(
308:                     "Telegram API: TCP connection OK."
309:                 )
310:
311:             except (
312:                 TimeoutError,
313:                 socket.timeout,
314:                 ConnectionError,
315:                 ConnectionResetError,
316:                 ConnectionAbortedError,
317:                 ConnectionRefusedError,
318:                 OSError,
319:             ) as error:
320:
321:                 print(
322:                     "Telegram API: TCP connection failed:"
323:                 )
324:
325:                 print(
326:                     f"{type(error).__name__}: {error}"
327:                 )
328:
329:                 raise
330:
331:             # ------------------------------------------------
332:             # TLS HANDSHAKE
333:             # ------------------------------------------------
334:
335:             print(
336:                 "Telegram API: TLS handshake..."
337:             )
338:
339:             context = ssl.create_default_context()
340:
341:             try:
342:
343:                 tls_sock = context.wrap_socket(
344:                     sock,
345:                     server_hostname=TELEGRAM_HOST
346:                 )
347:
348:                 # Важно:
349:                 # после TLS handshake timeout также сохраняется.
350:                 tls_sock.settimeout(
351:                     telegram_api_timeout
352:                 )
353:
354:                 print(
355:                     "Telegram API: TLS OK."
356:                 )
357:
358:             except (
359:                 TimeoutError,
360:                 socket.timeout,
361:                 ConnectionError,
362:                 ConnectionResetError,
363:                 ConnectionAbortedError,
364:                 ConnectionRefusedError,
365:                 OSError,
366:             ) as error:
367:
368:                 print(
369:                     "Telegram API: TLS connection failed:"
370:                 )
371:
372:                 print(
373:                     f"{type(error).__name__}: {error}"
374:                 )
375:
376:                 raise
377:
378:             # ------------------------------------------------
379:             # HTTP REQUEST
380:             # ------------------------------------------------
381:
382:             request = (
383:                 f"GET {path} HTTP/1.1\r\n"
384:                 f"Host: {TELEGRAM_HOST}\r\n"
385:                 f"User-Agent: CENSURU.NET-Bot/1.0\r\n"
386:                 f"Connection: close\r\n"
387:                 f"\r\n"
388:             )
389:
390:             print(
391:                 "Telegram API: sending HTTP request..."
392:             )
393:
394:             try:
395:
396:                 tls_sock.sendall(
397:                     request.encode("ascii")
398:                 )
399:
400:             except (
401:                 TimeoutError,
402:                 socket.timeout,
403:                 ConnectionError,
404:                 ConnectionResetError,
405:                 ConnectionAbortedError,
406:                 ConnectionRefusedError,
407:                 OSError,
408:             ) as error:
409:
410:                 print(
411:                     "Telegram API: HTTP send failed:"
412:                 )
413:
414:                 print(
415:                     f"{type(error).__name__}: {error}"
416:                 )
417:
418:                 raise
419:
420:             # ------------------------------------------------
421:             # HTTP RESPONSE
422:             # ------------------------------------------------
423:
424:             print(
425:                 "Telegram API: waiting for response..."
426:             )
427:
428:             response = b""
429:
430:             try:
431:
432:                 while True:
433:
434:                     chunk = tls_sock.recv(
435:                         8192
436:                     )
437:
438:                     if not chunk:
439:                         break
440:
441:                     response += chunk
442:
443:             except (
444:                 TimeoutError,
445:                 socket.timeout,
446:                 ConnectionError,
447:                 ConnectionResetError,
448:                 ConnectionAbortedError,
449:                 ConnectionRefusedError,
450:                 OSError,
451:             ) as error:
452:
453:                 print(
454:                     "Telegram API: HTTP receive failed:"
455:                 )
456:
457:                 print(
458:                     f"{type(error).__name__}: {error}"
459:                 )
460:
461:                 raise
462:
463:             if b"\r\n\r\n" not in response:
464:
465:                 raise RuntimeError(
466:                     "Telegram вернул "
467:                     "некорректный HTTP-ответ."
468:                 )
469:
470:             header, body = response.split(
471:                 b"\r\n\r\n",
472:                 1
473:             )
474:
475:             result = json.loads(
476:                 body.decode(
477:                     "utf-8",
478:                     errors="replace"
479:                 )
480:             )
481:
482:             print(
483:                 "Telegram API: запрос успешен."
484:             )
485:
486:             return result
487:
488:         except (
489:             TimeoutError,
490:             socket.timeout,
491:             ConnectionError,
492:             ConnectionResetError,
493:             ConnectionAbortedError,
494:             ConnectionRefusedError,
495:             OSError,
496:         ) as error:
497:
498:             last_error = error
499:
500:             error_text = str(error)
501:
502:             # ------------------------------------------------
503:             # Windows error diagnostics
504:             # ------------------------------------------------
505:
506:             win_error = getattr(
507:                 error,
508:                 "winerror",
509:                 None
510:             )
511:
512:             if win_error is not None:
513:
514:                 error_label = (
515:                     f"WinError {win_error}"
516:                 )
517:
518:             else:
519:
520:                 error_label = (
521:                     f"{type(error).__name__}"
522:                 )
523:
524:             print()
525:
526:             print(
527:                 "Telegram API: сетевой сбой "
528:                 f"на попытке {attempt}/"
529:                 f"{telegram_api_retries}:"
530:             )
531:
532:             print(
533:                 f"{error_label}: {error_text}"
534:             )
535:
536:             # ------------------------------------------------
537:             # WINERROR 10051
538:             #
539:             # Windows сообщает, что сеть/маршрут
540:             # временно недоступны.
541:             #
542:             # Бессмысленно делать длинные retries:
543:             # следующая попытка всё равно может сразу
544:             # получить тот же локальный сетевой сбой.
545:             #
546:             # Для последней попытки ошибка всё равно
547:             # будет выброшена ниже.
548:             # ------------------------------------------------
549:
550:             if (
551:                 win_error == 10051
552:                 and attempt < telegram_api_retries
553:             ):
554:
555:                 print(
556:                     "Telegram API: Windows сообщает "
557:                     "об отсутствии сетевого маршрута."
558:                 )
559:
560:                 print(
561:                     "Telegram API: следующая попытка "
562:                     "будет выполнена без увеличения timeout."
563:                 )
564:
565:             if attempt >= telegram_api_retries:
566:
567:                 raise
568:
569:         except Exception:
570:
571:             raise
572:
573:         finally:
574:
575:             if tls_sock is not None:
576:
577:                 try:
578:
579:                     tls_sock.close()
580:
581:                 except Exception:
582:
583:                     pass
584:
585:             elif sock is not None:
586:
587:                 try:
588:
589:                     sock.close()
590:
591:                 except Exception:
592:
593:                     pass
594:
595:     if last_error is not None:
596:
597:         raise last_error
598:
599:     raise RuntimeError(
600:         "Telegram API: запрос завершился "
601:         "без результата."
602:     )
603: # ============================================================
604: # TELEGRAM HELPERS
605: # ============================================================
606:
607: # ============================================================
608: # STATUS MESSAGE STATE
609: # ============================================================
610:
611: _STATUS_MESSAGES = {}
612:
613: # Ожидающие выбора режима загрузки.
614: #
615: # Формат:
616: # {
617: #     chat_id: {
618: #         "url": "...",
619: #         "kind": "track" | "yandex_playlist" | "youtube_playlist"
620: #     }
621: # }
622: _PENDING_DOWNLOADS = {}
623:
624: _STATUS_LOCK = threading.Lock()
625:

C:\Users\Константин\OneDrive\Desktop\цензуры.нет (вынес ск)\engine>python -c "from pathlib import Path; lines=Path('bot.py').read_text(encoding='utf-8').splitlines(); print('\n'.join(f'{i+1}: {lines[i]}' for i in range(2950,3075)))"
2951:
2952:         updates = response.get(
2953:             "result",
2954:             []
2955:         )
2956:
2957:         for update in updates:
2958:
2959:             offset = (
2960:                 update["update_id"] + 1
2961:             )
2962:
2963:             # ------------------------------------------------
2964:             # CALLBACK: выбор режима скачивания
2965:             # ------------------------------------------------
2966:
2967:             callback_query = update.get(
2968:                 "callback_query"
2969:             )
2970:
2971:             if callback_query:
2972:                 callback_id = callback_query.get(
2973:                     "id"
2974:                 )
2975:
2976:                 callback_data = callback_query.get(
2977:                     "data",
2978:                     ""
2979:                 )
2980:
2981:                 callback_message = callback_query.get(
2982:                     "message",
2983:                     {}
2984:                 )
2985:
2986:                 callback_chat = callback_message.get(
2987:                     "chat",
2988:                     {}
2989:                 )
2990:
2991:                 callback_chat_id = callback_chat.get(
2992:                     "id"
2993:                 )
2994:
2995:                 print()
2996:                 print(
2997:                     "[CALLBACK]",
2998:                     callback_chat_id,
2999:                     callback_data
3000:                 )
3001:
3002:                 if callback_id:
3003:                     try:
3004:                         answer_callback_query(
3005:                             callback_id
3006:                         )
3007:                     except Exception as callback_error:
3008:                         print(
3009:                             "Ошибка answerCallbackQuery:",
3010:                             callback_error
3011:                         )
3012:
3013:                 if (
3014:                     callback_chat_id
3015:                     and callback_data.startswith(
3016:                         "mode:"
3017:                     )
3018:                 ):
3019:                     parts = callback_data.split(
3020:                         ":"
3021:                     )
3022:
3023:                     if len(parts) == 3:
3024:                         selected_mode = parts[1]
3025:                         selected_lrc = (
3026:                             parts[2] == "1"
3027:                         )
3028:
3029:                         if selected_mode not in (
3030:                             "normal",
3031:                             "uncensored"
3032:                         ):
3033:                             print(
3034:                                 "ОШИБКА: неизвестный mode:",
3035:                                 selected_mode
3036:                             )
3037:                             continue
3038:
3039:                         pending = _PENDING_DOWNLOADS.pop(
3040:                             callback_chat_id,
3041:                             None
3042:                         )
3043:
3044:                         if not pending:
3045:                             send_message(
3046:                                 callback_chat_id,
3047:                                 "Запрос устарел. Отправьте ссылку заново."
3048:                             )
3049:                             continue
3050:
3051:                         pending_url = pending["url"]
3052:                         pending_kind = pending["kind"]
3053:
3054:                         send_message(
3055:                             callback_chat_id,
3056:                             (
3057:                                 "Режим выбран.\n\n"
3058:                                 f"Режим: "
3059:                                 f"{'обычный' if selected_mode == 'normal' else 'без цензуры'}\n"
3060:                                 f"LRC: "
3061:                                 f"{'включён' if selected_lrc else 'выключен'}\n\n"
3062:                                 "Начинаю обработку..."
3063:                             )
3064:                         )
3065:
3066:                         start_download_request(
3067:                             callback_chat_id,
3068:                             pending_url,
3069:                             pending_kind,
3070:                             selected_mode,
3071:                             selected_lrc
3072:                         )
3073:
3074:                         continue
3075:
