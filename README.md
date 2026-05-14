Предварительно сгенерить ключи:

```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
```

```bash
chmod +x ssh/setup-ssh.sh
chmod +x mail/setup-mail.sh

docker compose up -d
```

ssh:

```bash
ssh -p 2222 student@127.0.0.1
```