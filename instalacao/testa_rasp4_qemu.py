"""Sobe uma imagem do Raspberry Pi 4 (Ubuntu raspi) no QEMU, máquina raspi4b, sem o Pi.

Roda no Windows com o QEMU para Windows (https://qemu.weilnetz.de/w64/, 9.0 ou mais novo; testado
com o 11.1). A imagem não é alterada: o QEMU grava numa camada qcow2 ao lado do LOG (o cartão
emulado precisa ter tamanho potência de 2, e a camada resolve isso também).

    python testa_rasp4_qemu.py IMAGEM.img PASTA_BOOT LOG [espera_s]

PASTA_BOOT = os arquivos da partição FAT da imagem (vmlinuz, initrd.img, bcm2711-rpi-4-b.dtb).
Para tirar sem Linux: 7-Zip, abrindo a .img (ela aparece como 0.fat, 1.img...).

O teste não faz login: um diagnóstico vai pela linha do kernel (systemd.run=), espera `espera_s`
segundos depois do boot, escreve na serial (LOG) entre ===DIAG=== e ===FIM=== e desliga.

O que o emulador não tem: PCIe (USB), rede, Wi-Fi, GPU. Os drivers de câmera/ISP/codec do Pi
travam o udev no QEMU; por padrão eles ficam bloqueados (só nesta linha de comando, não na
imagem). O emulador é lento: espere pelo menos uns 15 min (padrão: 20).
"""
import gzip, os, shutil, subprocess, sys, time

img, boot, log = sys.argv[1], sys.argv[2], sys.argv[3]
espera = int(sys.argv[4]) if len(sys.argv) > 4 else 1200
Q = os.environ.get("QEMU", r"C:\Program Files\qemu")

# o vmlinuz do Ubuntu é gzip: o QEMU do raspi4b precisa do Image descompactado
kernel = os.path.join(os.path.dirname(os.path.abspath(log)), "Image")
if not os.path.exists(kernel):
    with gzip.open(os.path.join(boot, "vmlinuz")) as f, open(kernel, "wb") as o:
        shutil.copyfileobj(f, o)

ovl = os.path.splitext(log)[0] + ".qcow2"
if os.path.exists(ovl):
    os.remove(ovl)
subprocess.run([os.path.join(Q, "qemu-img.exe"), "create", "-q", "-f", "qcow2", "-F", "raw",
                "-b", os.path.abspath(img), ovl, "32G"], check=True)

# sem aspas duplas aqui dentro (o systemd.run= vai entre aspas duplas na linha do kernel)
# o systemd.run= troca o alvo padrão pela unidade dele: sem o start do multi-user.target o boot
# para no sysinit.target (sem dbus, ssh, serviços do usuário...)
diag = ("systemctl start --no-block multi-user.target; "
        "sleep %d; exec >/dev/console 2>&1; echo; echo ===DIAG===; "
        "findmnt -o TARGET,SOURCE,FSTYPE,OPTIONS; echo ---; "
        "systemctl is-system-running; systemctl --failed --no-legend --no-pager; echo ---; "
        "systemctl list-jobs --no-pager | head -25; echo ---; "
        "touch /teste_rw && echo RAIZ_GRAVAVEL || echo RAIZ_SOMENTE_LEITURA; "
        "touch /boot/firmware/teste_rw && echo BOOT_GRAVAVEL || echo BOOT_SOMENTE_LEITURA; "
        "touch /home/teste_rw && echo HOME_GRAVAVEL && rm /home/teste_rw; echo ---; "
        "systemctl is-active ssh cbr-firewall systemd-timesyncd user@1000 var-log-esqueleto; "
        "systemctl --user -M rasp@ --no-pager --all list-units --no-legend | grep -e cbr -e failed; echo ---; "
        "journalctl -b --no-pager | grep -i -e read-only -e erofs | grep -v teste_rw | cut -c1-200 | tail -40; echo ---; "
        "df -h / /home /var/log /tmp; "
        "echo ===FIM===" % espera)
bloqueia = ("bcm2835_codec,bcm2835_isp,bcm2835_v4l2,vc_sm_cma,bcm2835_mmal_vchiq,rpivid_hevc,"
            "snd_bcm2835,bcm2835_unicam")
# no raspi4b do QEMU a PL011 vira ttyAMA1; sem uma console que exista, o initramfs dá kernel panic
append = ("earlycon=pl011,mmio32,0xfe201000 console=ttyAMA1,115200 root=LABEL=writable "
          "rootfstype=ext4 rootwait fixrtc fsck.repair=yes module_blacklist=%s "
          "systemd.run=\"/bin/sh -c '%s'\"" % (bloqueia, diag))
cmd = [os.path.join(Q, "qemu-system-aarch64.exe"), "-M", "raspi4b",
       "-kernel", kernel, "-initrd", os.path.join(boot, "initrd.img"),
       "-dtb", os.path.join(boot, "bcm2711-rpi-4-b.dtb"), "-append", append,
       "-drive", "file=%s,format=qcow2,if=sd" % ovl,
       "-display", "none", "-monitor", "none", "-serial", "file:" + log]
t = time.time()
print("QEMU rodando; serial em", log, flush=True)
try:
    # o desligamento às vezes trava (udev preso no emulador): não espera mais que espera + 30 min
    subprocess.run(cmd, timeout=espera + 1800)
except subprocess.TimeoutExpired:
    print("QEMU não desligou sozinho; encerrado")
print("fim em %.0f s" % (time.time() - t))
