self.addEventListener('install', event => {
    console.log('Service Worker: Installiert');
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    console.log('Service Worker: Aktiviert');
    event.waitUntil(clients.claim());
});

self.addEventListener('message', event => {
    if (event.data && event.data.action === 'startDailyReminder') {
        const title = "MAYA Erinnerung";
        const options = {
            body: "Es ist Zeit für dein tägliches Foto! 📸",
            icon: "/static/icon.png",
            vibrate: [200, 100, 200]
        };

        // Moderne Chrome/Android Unterstützung für Notification Triggers API
        if ('showTrigger' in Notification.prototype) {
            // Plane Benachrichtigung in genau 24 Stunden (86400000 ms)
            options.showTrigger = new TimestampTrigger(Date.now() + 24 * 60 * 60 * 1000);

            self.registration.showNotification(title, options)
                .then(() => console.log("Tägliche Benachrichtigung (Trigger) gestartet."))
                .catch(err => console.error("Fehler beim Planen der Benachrichtigung:", err));
        } else {
            // Fallback: Zeigt für Testzwecke sofort eine Notification an.
            // Echtes Push erfordert in Safari/Firefox serverseitiges Web Push.
            options.body += "\n(Test-Push. Für echte wiederkehrende Pushs ist ein Server-Push-Abo oder die Trigger API nötig.)";
            self.registration.showNotification(title, options);
        }
    }
});

self.addEventListener('notificationclick', event => {
    event.notification.close();
    event.waitUntil(
        clients.matchAll({ type: "window" }).then(clientList => {
            for (let i = 0; i < clientList.length; i++) {
                let client = clientList[i];
                if (client.url === '/' && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow('/');
            }
        })
    );
});
