#!/bin/bash
# تفعيل سجل مفصل (العنوان + المسار + الرد + هوية المتصل) لكشف ما يطلبه تطبيق iOS
set -e
cat > /etc/nginx/conf.d/vhostlog.conf <<'EOF'
log_format vhostfmt '$host | $status | "$request" | $remote_addr | "$http_user_agent"';
access_log /var/log/nginx/vhost.log vhostfmt;
EOF
nginx -t && systemctl reload nginx
: > /var/log/nginx/vhost.log
echo "السجل المفصل مفعّل ✓"
echo ""
echo "الآن: أغلق التطبيق على الهاتف تماماً ثم افتحه (وستظهر الشاشة البيضاء)، وبعدها شغّل:"
echo "  tail -25 /var/log/nginx/vhost.log"
