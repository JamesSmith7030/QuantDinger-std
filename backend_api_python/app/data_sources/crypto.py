"""
加密货币数据源
使用 CCXT (Coinbase) 获取数据
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
import ccxt

from app.data_sources.base import BaseDataSource, TIMEFRAME_SECONDS
from app.utils.logger import get_logger
from app.config import CCXTConfig, APIKeys

logger = get_logger(__name__)


class CryptoDataSource(BaseDataSource):
    """加密货币数据源"""
    
    name = "Crypto/CCXT"
    
    # 时间周期映射
    TIMEFRAME_MAP = CCXTConfig.TIMEFRAME_MAP
    
    # 常见的报价货币列表（按优先级排序）
    COMMON_QUOTES = ['USDT', 'USD', 'BTC', 'ETH', 'BUSD', 'USDC', 'BNB', 'EUR', 'GBP']
    
    def __init__(self):
        config = {
            'timeout': CCXTConfig.TIMEOUT,
            'enableRateLimit': CCXTConfig.ENABLE_RATE_LIMIT
        }
        
        # 如果配置了代理
        if CCXTConfig.PROXY:
            config['proxies'] = {
                'http': CCXTConfig.PROXY,
                'https': CCXTConfig.PROXY
            }
        
        exchange_id = CCXTConfig.DEFAULT_EXCHANGE
        
        # 动态加载交易所类
        if not hasattr(ccxt, exchange_id):
            logger.warning(f"CCXT exchange '{exchange_id}' not found, falling back to 'coinbase'")
            exchange_id = 'coinbase'
            
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class(config)
        
        # 延迟加载 markets（首次使用时加载）
        self._markets_loaded = False
        self._markets_cache = None
    
    def _ensure_markets_loaded(self) -> bool:
        """确保 markets 已加载（用于符号验证）"""
        if self._markets_loaded and self._markets_cache is not None:
            return True
        
        try:
            # 某些交易所需要显式加载 markets
            if hasattr(self.exchange, 'load_markets'):
                self.exchange.load_markets(reload=False)
            self._markets_cache = getattr(self.exchange, 'markets', {})
            self._markets_loaded = True
            return True
        except Exception as e:
            logger.debug(f"Failed to load markets for {self.exchange.id}: {e}")
            return False
    
    def _normalize_symbol(self, symbol: str) -> Tuple[str, str]:
        """
        规范化符号格式，返回 (normalized_symbol, base_currency)
        
        处理各种输入格式：
        - BTC/USDT -> BTC/USDT
        - BTCUSDT -> BTC/USDT
        - BTC/USDT:USDT -> BTC/USDT
        - BTC -> BTC/USDT (默认)
        - PI, TRX -> PI/USDT, TRX/USDT
        """
        if not symbol:
            return '', ''
        
        sym = symbol.strip()
        
        # 移除 swap/futures 后缀
        if ':' in sym:
            sym = sym.split(':', 1)[0]
        
        sym = sym.upper()
        
        # 如果已经有分隔符，直接解析
        if '/' in sym:
            parts = sym.split('/', 1)
            base = parts[0].strip()
            quote = parts[1].strip() if len(parts) > 1 else ''
            if base and quote:
                return f"{base}/{quote}", base
        
        # 尝试从常见报价货币中识别
        for quote in self.COMMON_QUOTES:
            if sym.endswith(quote) and len(sym) > len(quote):
                base = sym[:-len(quote)]
                if base:
                    return f"{base}/{quote}", base
        
        # 如果无法识别，默认使用 USDT
        return f"{sym}/USDT", sym
    
    def _find_valid_symbol(self, base: str, preferred_quote: str = 'USDT') -> Optional[str]:
        """
        在交易所的 markets 中查找有效的符号
        
        Args:
            base: 基础货币（如 'PI', 'TRX'）
            preferred_quote: 首选的报价货币
            
        Returns:
            找到的有效符号，如果找不到则返回 None
        """
        if not self._ensure_markets_loaded():
            return None
        
        markets = self._markets_cache or {}
        if not markets:
            return None
        
        # 按优先级尝试不同的报价货币
        quotes_to_try = [preferred_quote] + [q for q in self.COMMON_QUOTES if q != preferred_quote]
        
        for quote in quotes_to_try:
            candidate = f"{base}/{quote}"
            if candidate in markets:
                market = markets[candidate]
                # 检查市场是否活跃
                if market.get('active', True):
                    return candidate
        
        return None
    
    def _normalize_symbol_for_exchange(self, symbol: str) -> str:
        """
        根据交易所特性规范化符号
        
        不同交易所的符号格式要求：
        - Binance: BTC/USDT (标准格式)
        - OKX: BTC/USDT (标准格式，但某些币种可能不支持)
        - Coinbase: BTC/USD (通常使用 USD 而不是 USDT)
        - Kraken: XBT/USD (BTC 映射为 XBT)
        """
        normalized, base = self._normalize_symbol(symbol)
        
        if not normalized or not base:
            return symbol
        
        exchange_id = getattr(self.exchange, 'id', '').lower()
        
        # 特殊处理：某些交易所的符号映射
        if exchange_id == 'coinbase':
            # Coinbase 通常使用 USD 而不是 USDT
            if normalized.endswith('/USDT'):
                usd_version = normalized.replace('/USDT', '/USD')
                if self._ensure_markets_loaded():
                    markets = self._markets_cache or {}
                    if usd_version in markets:
                        return usd_version
        
        # 尝试在交易所中查找有效符号
        if self._ensure_markets_loaded():
            valid_symbol = self._find_valid_symbol(base, normalized.split('/')[1] if '/' in normalized else 'USDT')
            if valid_symbol:
                return valid_symbol
        
        return normalized

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get latest ticker for a crypto symbol via CCXT.

        Accepts common formats:
        - BTC/USDT, BTCUSDT, BTC/USDT:USDT
        - PI, TRX (will be normalized and searched across exchanges)
        - 自动适配不同交易所的符号格式要求
        """
        if not symbol or not symbol.strip():
            return {'last': 0, 'symbol': symbol}
        
        # 规范化符号
        normalized = self._normalize_symbol_for_exchange(symbol)
        
        if not normalized:
            logger.warning(f"Failed to normalize symbol: {symbol}")
            return {'last': 0, 'symbol': symbol}
        
        # 尝试获取 ticker
        try:
            ticker = self.exchange.fetch_ticker(normalized)
            if ticker and isinstance(ticker, dict):
                return ticker
        except Exception as e:
            error_msg = str(e).lower()
            is_symbol_error = any(keyword in error_msg for keyword in [
                'does not have market symbol',
                'symbol not found',
                'invalid symbol',
                'market does not exist',
                'trading pair not found'
            ])
            
            if is_symbol_error:
                # 尝试查找替代符号
                base = normalized.split('/')[0] if '/' in normalized else normalized
                if self._ensure_markets_loaded():
                    valid_symbol = self._find_valid_symbol(base)
                    if valid_symbol and valid_symbol != normalized:
                        try:
                            logger.debug(f"Trying alternative symbol: {valid_symbol} (original: {symbol}, first attempt: {normalized})")
                            ticker = self.exchange.fetch_ticker(valid_symbol)
                            if ticker and isinstance(ticker, dict):
                                return ticker
                        except Exception as e2:
                            logger.debug(f"Alternative symbol {valid_symbol} also failed: {e2}")
            
            # 如果所有尝试都失败，记录警告并返回默认值
            logger.warning(
                f"Symbol '{symbol}' (normalized: {normalized}) not found on {self.exchange.id}. "
                f"Error: {str(e)[:100]}"
            )
        
        return {'last': 0, 'symbol': symbol}
    
    def get_kline(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        before_time: Optional[int] = None,
        after_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """获取加密货币K线数据"""
        klines = []
        
        try:
            ccxt_timeframe = self.TIMEFRAME_MAP.get(timeframe, '1d')
            
            # 使用统一的符号规范化方法
            symbol_pair = self._normalize_symbol_for_exchange(symbol)
            
            if not symbol_pair:
                logger.warning(f"Failed to normalize symbol for K-line: {symbol}")
                return []
            
            # logger.info(f"获取加密货币K线: {symbol_pair}, 周期: {ccxt_timeframe}, 条数: {limit}")
            
            ohlcv = self._fetch_ohlcv(
                symbol_pair, ccxt_timeframe, limit, before_time, timeframe, after_time
            )
            
            if not ohlcv:
                logger.warning(f"CCXT returned no K-lines: {symbol_pair}")
                return []
            
            # 转换数据格式
            for candle in ohlcv:
                if len(candle) < 6:
                    continue
                klines.append(self.format_kline(
                    timestamp=int(candle[0] / 1000),  # 毫秒转秒
                    open_price=candle[1],
                    high=candle[2],
                    low=candle[3],
                    close=candle[4],
                    volume=candle[5]
                ))
            
            # 过滤和限制（回测带 after_time 时保留整段窗口，避免 [-limit:] 丢掉左端历史）
            klines = self.filter_and_limit(
                klines,
                limit,
                before_time,
                after_time,
                truncate=(after_time is None),
            )

            # 记录结果
            self.log_result(symbol, klines, timeframe)

            # Concise trace so backtest logs can correlate requested window with actual window
            if klines:
                try:
                    from datetime import datetime as _dt
                    first_ts = _dt.utcfromtimestamp(klines[0]['time']).isoformat()
                    last_ts = _dt.utcfromtimestamp(klines[-1]['time']).isoformat()
                    logger.info(
                        f"[CryptoKline] {symbol} {timeframe} returned {len(klines)} candles, "
                        f"utc_range={first_ts}~{last_ts}, limit={limit}, before_time={before_time}"
                    )
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Failed to fetch crypto K-lines {symbol}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        return klines
    
    def _fetch_ohlcv(
        self,
        symbol_pair: str,
        ccxt_timeframe: str,
        limit: int,
        before_time: Optional[int],
        timeframe: str,
        after_time: Optional[int] = None,
    ) -> List:
        """获取OHLCV数据（支持分页获取完整数据）"""
        try:
            if before_time:
                # 计算时间范围（UTC，与交易所 OHLCV 毫秒时间戳一致）
                total_seconds = self.calculate_time_range(timeframe, limit)
                # 回测里 before_time = end_date+1 天，常比「当前时刻」更晚；Coinbase 会报
                # start must not be in the future（其 start 指查询上界/窗口边界）
                now_ts = int(datetime.now(timezone.utc).timestamp())
                safe_before_ts = min(int(before_time), now_ts)
                if safe_before_ts < int(before_time):
                    logger.debug(
                        "CCXT OHLCV: clamped before_time %s -> %s (utc now cap for exchange)",
                        before_time,
                        safe_before_ts,
                    )
                end_dt = datetime.fromtimestamp(safe_before_ts, tz=timezone.utc)
                start_dt = end_dt - timedelta(seconds=total_seconds)
                if after_time is not None:
                    floor_dt = datetime.fromtimestamp(int(after_time), tz=timezone.utc)
                    start_dt = min(start_dt, floor_dt)
                timeframe_ms = TIMEFRAME_SECONDS.get(timeframe, 86400) * 1000
                now_ms = now_ts * 1000
                since = int(start_dt.timestamp() * 1000)
                if since >= now_ms:
                    since = max(0, now_ms - timeframe_ms)
                end_ms = safe_before_ts * 1000

                all_ohlcv: List[List[Any]] = []
                batch_limit = 300  # Coinbase limit is often 300, safer than 1000
                current_since = since
                max_batches = 6000
                empty_streak = 0
                max_empty = 6

                for _ in range(max_batches):
                    if current_since >= end_ms:
                        break
                    batch = self.exchange.fetch_ohlcv(
                        symbol_pair,
                        ccxt_timeframe,
                        since=current_since,
                        limit=batch_limit,
                    )
                    if not batch:
                        empty_streak += 1
                        if empty_streak >= max_empty:
                            break
                        # 跳过可能的空档，避免卡死在同一 since
                        current_since += timeframe_ms * min(batch_limit, 64)
                        continue
                    empty_streak = 0
                    all_ohlcv.extend(batch)
                    last_timestamp = batch[-1][0]
                    if last_timestamp >= end_ms:
                        break
                    next_since = last_timestamp + timeframe_ms
                    if next_since <= current_since:
                        break
                    current_since = next_since

                # 按开盘时间去重并排序，防止分页重叠
                by_ts = {int(row[0]): row for row in all_ohlcv if row and len(row) >= 6}
                ohlcv = sorted(by_ts.values(), key=lambda r: r[0])
            else:
                ohlcv = self.exchange.fetch_ohlcv(symbol_pair, ccxt_timeframe, limit=limit)
            
            # logger.info(f"CCXT 返回 {len(ohlcv) if ohlcv else 0} 条数据")
            return ohlcv
            
        except Exception as e:
            logger.warning(f"CCXT fetch_ohlcv failed: {str(e)}; trying fallback")
            return self._fetch_ohlcv_fallback(
                symbol_pair, ccxt_timeframe, limit, before_time, timeframe, after_time
            )
    
    def _fetch_ohlcv_fallback(
        self,
        symbol_pair: str,
        ccxt_timeframe: str,
        limit: int,
        before_time: Optional[int],
        timeframe: str,
        after_time: Optional[int] = None,
    ) -> List:
        """备用获取方法"""
        try:
            total_seconds = self.calculate_time_range(timeframe, limit)
            
            if before_time:
                now_ts = int(datetime.now(timezone.utc).timestamp())
                safe_before_ts = min(int(before_time), now_ts)
                end_dt = datetime.fromtimestamp(safe_before_ts, tz=timezone.utc)
                start_dt = end_dt - timedelta(seconds=total_seconds)
                if after_time is not None:
                    floor_dt = datetime.fromtimestamp(int(after_time), tz=timezone.utc)
                    start_dt = min(start_dt, floor_dt)
                tf_ms = TIMEFRAME_SECONDS.get(timeframe, 86400) * 1000
                now_ms = now_ts * 1000
                since = int(start_dt.timestamp() * 1000)
                if since >= now_ms:
                    since = max(0, now_ms - tf_ms)
            else:
                since = int((datetime.now() - timedelta(seconds=total_seconds)).timestamp() * 1000)
            
            ohlcv = self.exchange.fetch_ohlcv(symbol_pair, ccxt_timeframe, since=since, limit=limit)
            # logger.info(f"CCXT 备用方法返回 {len(ohlcv) if ohlcv else 0} 条数据")
            return ohlcv
        except Exception as e:
            logger.error(f"CCXT fallback method also failed: {str(e)}")
            return []

