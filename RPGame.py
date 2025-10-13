import pygame
import random
import math
import sys

# --- Configuración ---
WIDTH, HEIGHT = 1920, 1080  # Resolución Full HD
FPS = 60

PLAYER_SIZE = 48
PLAYER_COLOR = (0, 120, 255)
BG_COLOR = (180, 180, 180)
COIN_COLOR = (255, 215, 0)
HOUSE_COLOR = (150, 90, 50)
NPC_COLOR = (255, 200, 120)
CHEST_COLOR = (200, 160, 60)

COIN_RADIUS = 10
NUM_INITIAL_COINS = 12

MAX_HEALTH = 100

# --- Clases ---
class Item:
    def __init__(self, name, itype='misc', power=0, heal=0, price=0, desc=''):
        self.name = name
        self.itype = itype  # 'weapon','consumable','accessory','misc'
        self.power = power
        self.heal = heal
        self.price = price
        self.desc = desc

    def __repr__(self):
        return f"Item({self.name})"

class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, PLAYER_SIZE, PLAYER_SIZE)
        self.speed = 250.0
        self.health = MAX_HEALTH
        self.xp = 0
        self.level = 1
        self.coins = 20
        self.weapon = None
        self.inventory = []

    def handle_input(self, keys, dt, allow_move=True):
        if not allow_move:
            return
        vx = vy = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            vx = -1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            vx = 1
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            vy = -1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            vy = 1

        if vx != 0 and vy != 0:
            norm = math.sqrt(2) / 2
            vx *= norm
            vy *= norm

        dx = vx * self.speed * dt
        dy = vy * self.speed * dt

        self.rect.x += int(dx)
        self.rect.y += int(dy)

        # límites pantalla
        self.rect.left = max(0, self.rect.left)
        self.rect.top = max(0, self.rect.top)
        self.rect.right = min(WIDTH, self.rect.right)
        self.rect.bottom = min(HEIGHT - 20, self.rect.bottom)  # <-- antes era HEIGHT


class Coin:
    def __init__(self, x, y):
        self.pos = (x, y)
        self.radius = COIN_RADIUS

class NPC:
    def __init__(self, x, y, name, dialog, xp_reward=0, merchant=False, shop_items=None, inside=False):
        self.rect = pygame.Rect(x, y, 36, 46)
        self.name = name
        self.dialog = dialog
        self.talked = False
        self.xp_reward = xp_reward
        self.merchant = merchant
        self.shop_items = shop_items or []
        self.inside = inside  # si este NPC está pensado para interiores

    def draw(self, surf, font):
        pygame.draw.rect(surf, NPC_COLOR, self.rect)
        nm = font.render(self.name, True, (10,10,10))
        surf.blit(nm, (self.rect.x - 6, self.rect.y - 18))

class House:
    def __init__(self, x, y, w, h, name='Casa', chest_items=None, interior_npcs=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.name = name
        self.chest_items = chest_items or []
        self.interior_npcs = interior_npcs or []
        # chest position (absolute)
        self.chest_rect = pygame.Rect(self.rect.centerx - 24, self.rect.centery - 12, 48, 32)

    def draw(self, surf):
        pygame.draw.rect(surf, HOUSE_COLOR, self.rect)
        # door hint
        door_txt = pygame.font.SysFont(None, 20).render('Puerta (E)', True, (0,0,0))
        surf.blit(door_txt, (self.rect.centerx - door_txt.get_width()//2, self.rect.bottom - 18))

# mensajes
class Log:
    def __init__(self, duration_ms=5000, padding=12, max_width=800):
        # Cola de mensajes pendientes (strings)
        self.queue = []
        # Mensaje actualmente mostrado (string) o None
        self.current = None
        # instante (ms) en que se empezó a mostrar current
        self.start_time = None
        # duración por mensaje en milisegundos
        self.duration = duration_ms
        # padding interior del cuadro
        self.padding = padding
        # ancho máximo del cuadro (se adapta si la pantalla es más estrecha)
        self.max_width = max_width

    def add(self, msg):
        """Añade un mensaje a la cola y, si no hay ninguno mostrándose, empieza a mostrarlo."""
        if not isinstance(msg, str):
            msg = str(msg)
        self.queue.append(msg)
        # si no hay ningún mensaje activo, arrancar el siguiente inmediatamente
        if self.current is None:
            self._next_message()

    def _next_message(self):
        """Pasa al siguiente mensaje de la cola o limpia si no hay."""
        if self.queue:
            self.current = self.queue.pop(0)
            self.start_time = pygame.time.get_ticks()
        else:
            self.current = None
            self.start_time = None

    def _wrap_text(self, text, font, max_w):
        """
        Ajusta 'text' en varias líneas para que no exceda max_w.
        Devuelve lista de líneas.
        """
        words = text.split(' ')
        lines = []
        cur = ''
        for w in words:
            test = cur + ('' if cur == '' else ' ') + w
            if font.size(test)[0] <= max_w:
                cur = test
            else:
                if cur == '':
                    # palabra individual demasiado larga -> cortamos
                    # la rompemos en trozos del tamaño máximo posible
                    tmp = w
                    piece = ''
                    for ch in tmp:
                        if font.size(piece + ch)[0] <= max_w:
                            piece += ch
                        else:
                            lines.append(piece)
                            piece = ch
                    if piece:
                        cur = piece
                    else:
                        cur = ''
                else:
                    lines.append(cur)
                    cur = w
        if cur:
            lines.append(cur)
        return lines

    def draw(self, surf, font):
        """
        Dibuja el cuadro de diálogo en la parte inferior de la pantalla si hay current != None.
        El cuadro desaparece automáticamente a los 5 s o al pasar al siguiente mensaje.
        Nunca se sale de la pantalla (ajustado para 1080p o cualquier resolución).
        """
        # Si no hay mensaje activo, no dibujar nada
        if self.current is None:
            return

        now = pygame.time.get_ticks()
        elapsed = now - (self.start_time or 0)

        # Si ha pasado el tiempo, pasar al siguiente mensaje o esconder
        if elapsed >= self.duration:
            self._next_message()
            # si no hay siguiente, salimos sin dibujar (el cuadro desaparece)
            if self.current is None:
                return
            now = pygame.time.get_ticks()
            elapsed = 0
            self.start_time = now

        # --- Calcular posición y tamaño del cuadro ---
        screen_w, screen_h = surf.get_size()
        margin_x = 40
        margin_bottom = 80   # margen extra para no solaparse con el jugador ni HUD
        max_box_h = int(screen_h * 0.35)  # máximo 35% de la altura de pantalla

        box_w = min(self.max_width, screen_w - 2 * margin_x)
        box_x = (screen_w - box_w) // 2
        max_text_w = box_w - 2 * self.padding

        lines = self._wrap_text(self.current, font, max_text_w)
        line_height = font.get_linesize()
        needed_h = line_height * len(lines) + 2 * self.padding
        box_h = min(needed_h, max_box_h)

        # Asegurar que el cuadro no se sale de la pantalla
        box_y = screen_h - margin_bottom - box_h
        if box_y + box_h > screen_h - 10:
            box_y = screen_h - box_h - 10

        # --- Dibujar cuadro estilo Pokémon ---
        pygame.draw.rect(surf, (10, 10, 10), (box_x, box_y, box_w, box_h))  # fondo oscuro
        pygame.draw.rect(surf, (220, 220, 220), (box_x + 4, box_y + 4, box_w - 8, box_h - 8))  # interior claro
        pygame.draw.rect(surf, (0, 0, 0), (box_x, box_y, box_w, box_h), 2)  # borde negro

        # --- Dibujar texto dentro del cuadro ---
        text_x = box_x + self.padding
        text_y = box_y + self.padding
        for line in lines:
            rendered = font.render(line, True, (10, 10, 10))
            surf.blit(rendered, (text_x, text_y))
            text_y += line_height

        # --- Dibujar barra de progreso (tiempo restante) ---
        progress_w = int((1.0 - (elapsed / self.duration)) * 80)
        pw = 84
        ph = 10
        px = box_x + box_w - pw - 12
        py = box_y + box_h - ph - 8

        pygame.draw.rect(surf, (150,150,150), (px, py, pw, ph), border_radius=3)
        pygame.draw.rect(surf, (60,180,60), (px + 2, py + 2, max(0, progress_w), ph - 4), border_radius=2)


# HUD
def draw_hud(screen, font, player):
    # vida
    pygame.draw.rect(screen, (200,50,50), (20, 20, 300, 26))
    inner = max(0, min(300, int(300 * (player.health / MAX_HEALTH))))
    pygame.draw.rect(screen, (50,200,50), (20, 20, inner, 26))
    pygame.draw.rect(screen, (0,0,0), (20,20,300,26), 2)
    hp_txt = font.render(f"HP: {int(player.health)}/{MAX_HEALTH}", True, (0,0,0))
    screen.blit(hp_txt, (330, 20))

    # XP simple
    xp_txt = font.render(f"XP: {int(player.xp)}  Nivel: {player.level}", True, (0,0,0))
    screen.blit(xp_txt, (20, 56))

    coin_txt = font.render(f"Monedas: {player.coins}", True, (0,0,0))
    screen.blit(coin_txt, (20, 86))

    weapon_txt = font.render(f"Arma: {player.weapon.name if player.weapon else 'Ninguna'}", True, (0,0,0))
    screen.blit(weapon_txt, (20, 112))

# --- Construcción del pueblo (zona chill) ---
def make_village():
    houses = []
    npcs = []

    # crear casas con cofres y NPCs interior/exterior
    h1 = House(120, 120, 260, 220, name='Casa del Herrero', chest_items=[Item('Rusty Sword','weapon',power=10,desc='Espada oxidada.')], interior_npcs=[NPC(0,0,'Herrero','Forja y venta de armas',xp_reward=6,inside=True)])
    h2 = House(420, 100, 260, 220, name='Casa del Panadero', chest_items=[Item('Loaf','consumable',heal=12,desc='Pan que restaura salud.')], interior_npcs=[NPC(0,0,'Panadero','Prueba mis panes',xp_reward=4,inside=True)])
    h3 = House(720, 140, 260, 220, name='Casa Mayor', chest_items=[Item('Bronze Ring','accessory',desc='Anillo sencillo.')], interior_npcs=[NPC(0,0,'Anciana','Recuerdo de viejos tiempos',xp_reward=5,inside=True)])
    h4 = House(220, 380, 260, 220, name='Casa del Cazador', chest_items=[Item('Short Bow','weapon',power=12,desc='Arco corto para ataques a distancia.')], interior_npcs=[NPC(0,0,'Cazador','Busca setas y animales',xp_reward=5,inside=True)])
    h5 = House(560, 380, 260, 220, name='Posada', chest_items=[Item('Potion','consumable',heal=30,price=6,desc='Poción de curación')], interior_npcs=[NPC(0,0,'Tabernera','Bienvenido a la posada',xp_reward=6,inside=True)])

    houses.extend([h1,h2,h3,h4,h5])

    # colocar NPCs exteriores y comerciantes
    npcs.append(NPC(220, 80, 'Aldeano', 'Hoy hace buen día.', xp_reward=2))
    npcs.append(NPC(480, 60, 'Jardinero', 'Cuida las plantas.' , xp_reward=2))
    npcs.append(NPC(820, 100, 'Anciano', 'Me chismorrea mi nieto...', xp_reward=3))

    # merchant with shop items
    shop_items = [Item('Steel Sword','weapon',power=22,price=25,desc='Espada decente.'), Item('Health Potion','consumable',heal=50,price=12,desc='Recupera HP')]
    merchant = NPC(440, 320, 'Mercader', 'Tengo cosas útiles. Pulsa E para comprar (si tienes monedas).', merchant=True, shop_items=shop_items)
    npcs.append(merchant)

    # assign interior NPC positions inside each house (absolute coords)
    for h in houses:
        # interior npc positions: place near top-left of interior
        ybase = h.rect.top + 50
        xbase = h.rect.left + 50
        for i, n in enumerate(h.interior_npcs):
            n.rect.x = xbase + i * 60
            n.rect.y = ybase
            n.inside = True

    return houses, npcs

# --- Main ---

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('RPG - Zona Chill (Aldea)')
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 26)
    big_font = pygame.font.SysFont(None, 36)

    player = Player(380, 500)
    coins = [Coin(random.randint(100, WIDTH-600), random.randint(120, HEIGHT-150)) for _ in range(NUM_INITIAL_COINS)]

    houses, npcs = make_village()
    log = Log()

    inside_house = None  # referencia a House
    shop_open = False
    current_shop = None

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_e:
                    # interacción
                    if inside_house:
                        # intentar abrir cofre si cerca
                        chest = inside_house.chest_rect
                        if player.rect.colliderect(chest):
                            if inside_house.chest_items:
                                item = inside_house.chest_items.pop(0)
                                player.inventory.append(item)
                                log.add(f'Has abierto un cofre y obtuviste: {item.name}')
                                # si es arma, sugerimos equiparla
                                if item.itype == 'weapon':
                                    player.weapon = item
                                    log.add(f'Has equipado temporalmente: {item.name}')
                            else:
                                log.add('El cofre está vacío.')
                        else:
                            # hablar con NPCs interiores si colisionan
                            talked = False
                            for n in inside_house.interior_npcs:
                                if player.rect.colliderect(n.rect):
                                    log.add(f'{n.name}: {n.dialog}')
                                    if not n.talked:
                                        player.xp += n.xp_reward
                                        n.talked = True
                                        log.add(f'Has ganado {n.xp_reward} XP por hablar.')
                                    talked = True
                                    break
                            if not talked:
                                # salir de la casa si no hay interacción
                                inside_house = None
                                log.add('Sales de la casa.')
                    else:
                        # fuera: comprobar NPCs
                        interacted = False
                        for n in npcs:
                            if player.rect.colliderect(n.rect):
                                if n.merchant:
                                    # abrir tienda
                                    shop_open = True
                                    current_shop = n
                                    log.add(f"Mercader: {n.dialog}")
                                    interacted = True
                                else:
                                    log.add(f'{n.name}: {n.dialog}')
                                    if not n.talked:
                                        player.xp += n.xp_reward
                                        n.talked = True
                                        log.add(f'Has ganado {n.xp_reward} XP por conversar.')
                                    interacted = True
                                break
                        if not interacted:
                            # entrar en una casa si estamos frente a ella
                            for h in houses:
                                door_rect = pygame.Rect(h.rect.centerx - 30, h.rect.bottom - 24, 60, 24)
                                if player.rect.colliderect(door_rect):
                                    inside_house = h
                                    # situar al player dentro en posición cómoda
                                    player.rect.centerx = h.rect.centerx
                                    player.rect.centery = h.rect.centery + 40
                                    log.add(f'Has entrado en {h.name}. Pulsa E para abrir el cofre o hablar con habitantes.')
                                    break

                # compras en tienda
                if shop_open and current_shop:
                    if event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                        idx = event.key - pygame.K_1
                        if idx < len(current_shop.shop_items):
                            item = current_shop.shop_items[idx]
                            if player.coins >= item.price:
                                player.coins -= item.price
                                player.inventory.append(item)
                                log.add(f'Has comprado: {item.name} por {item.price} monedas.')
                                # auto-equipar armas pequeñas
                                if item.itype == 'weapon' and not player.weapon:
                                    player.weapon = item
                                    log.add(f'Equipado: {item.name}')
                            else:
                                log.add('No tienes suficientes monedas.')
                # cerrar tienda con Q
                if event.key == pygame.K_q and shop_open:
                    shop_open = False
                    current_shop = None
                    log.add('Has cerrado la tienda.')

        keys = pygame.key.get_pressed()
        # si está abierta tienda o estamos dentro de casa y hay diálogo, podemos permitir movimiento de todos modos
        player.handle_input(keys, dt, allow_move=not shop_open)

        # recoger monedas solo fuera
        if not inside_house:
            for c in coins[:]:
                # limitar área de aparición para que no salgan por la derecha donde el log está
                if player.rect.collidepoint(c.pos):
                    coins.remove(c)
                    player.coins += 1
                    player.xp += 5
                    #log.add('Has recogido una moneda.')

        # dibujado
        # si estamos dentro de una casa dibujar interior diferente
        if inside_house:
            screen.fill((160, 130, 90))
            # texto interior
            title = big_font.render(f"Dentro: {inside_house.name}", True, (255,255,255))
            screen.blit(title, (40, 36))
            # dibujar cofres y NPCs interiores
            chest = inside_house.chest_rect
            pygame.draw.rect(screen, CHEST_COLOR, chest)
            txt = font.render('Cofre (E)', True, (0,0,0))
            screen.blit(txt, (chest.x, chest.y - 22))
            for n in inside_house.interior_npcs:
                n.draw(screen, font)

            # door hint to exit
            hint = font.render('Pulsa E para abrir cofres, hablar o salir', True, (255,255,255))
            screen.blit(hint, (40, 80))

        else:
            screen.fill((140, 200, 140))
            # dibujar casas
            for h in houses:
                h.draw(screen)
                # dibujar puerta área (invisible but helpful)
                door_rect = pygame.Rect(h.rect.centerx - 30, h.rect.bottom - 24, 60, 24)
                pygame.draw.rect(screen, (110, 70, 40), door_rect)

            # dibujar NPCs exteriores
            for n in npcs:
                n.draw(screen, font)

            # dibujar coins
            for c in coins:
                pygame.draw.circle(screen, COIN_COLOR, (int(c.pos[0]), int(c.pos[1])), c.radius)

            # señal para ir al bosque / boss (solo visual para ahora)
            forest_rect = pygame.Rect(40, HEIGHT - 260, 420, 220)
            pygame.draw.rect(screen, (34, 139, 34), forest_rect)
            forest_label = font.render('Bosque (F): aquí lidiarás con enemigos y loot', True, (255,255,255))
            screen.blit(forest_label, (forest_rect.x + 10, forest_rect.y + 10))

            boss_rect = pygame.Rect(WIDTH - 520, HEIGHT//2 - 160, 380, 320)
            pygame.draw.rect(screen, (120, 20, 120), boss_rect)
            boss_label = font.render('Zona Jefe (preparación requerida)', True, (255,255,255))
            screen.blit(boss_label, (boss_rect.x + 10, boss_rect.y + 10))

        # dibujar player
        pygame.draw.rect(screen, PLAYER_COLOR, player.rect)

        draw_hud(screen, font, player)
        log.draw(screen, font)

        # mostrar shop overlay si abierto
        if shop_open and current_shop:
            overlay = pygame.Surface((720, 420))
            overlay.set_alpha(230)
            overlay.fill((250,250,250))
            sx = WIDTH//2 - 360
            sy = HEIGHT//2 - 210
            screen.blit(overlay, (sx, sy))
            title = big_font.render(f'Tienda: {current_shop.name}', True, (10,10,10))
            screen.blit(title, (sx + 20, sy + 14))
            hint = font.render('Pulsa 1..5 para comprar | Q para salir', True, (10,10,10))
            screen.blit(hint, (sx + 20, sy + 60))
            # listar items
            y = sy + 100
            for i, it in enumerate(current_shop.shop_items):
                it_txt = font.render(f'{i+1}. {it.name} - {it.desc} - Precio: {it.price}', True, (10,10,10))
                screen.blit(it_txt, (sx + 40, y))
                y += 36

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()
