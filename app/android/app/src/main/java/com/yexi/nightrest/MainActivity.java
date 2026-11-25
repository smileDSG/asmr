package com.yexi.nightrest;

import android.os.Bundle;
import android.os.PowerManager;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    private PowerManager.WakeLock wakeLock;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 锁屏助眠时，屏幕会关闭但用户还要继续听声音。
        // PARTIAL_WAKE_LOCK 让 CPU 保持运行，避免系统休眠把音频掐断。
        // 只在应用内部持有，不点亮屏幕，耗电极低。
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        if (pm != null) {
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "yexi:sleep-playback");
            wakeLock.setReferenceCounted(false);
            wakeLock.acquire();
        }
    }

    @Override
    public void onDestroy() {
        // 应用真正退出时释放，避免一直占用
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
        super.onDestroy();
    }
}
