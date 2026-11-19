# Importe les outils de l'ORM : api (décorateurs), fields (types de champs), models (classe de base).
from odoo import api, fields, models


# =====================================================================
# Modèle « Salle de travail »
# =====================================================================
# Classe Python qui devient le modèle biblio.room (table biblio_room).
class BiblioRoom(models.Model):
    # Nom technique du modèle.
    _name = 'biblio.room'
    # Description lisible du modèle.
    _description = 'Salle de travail'
    # Tri par défaut des listes : par nom de salle.
    _order = 'name'

    # Nom de la salle, obligatoire.
    name = fields.Char('Salle', required=True)
    # Nombre de places.
    seats = fields.Integer('Places')
    # Prix de location par jour, obligatoire.
    daily_price = fields.Float('Prix par jour', required=True)
    # Les réservations de cette salle (côté « un » de la relation, l'inverse de room_id).
    booking_ids = fields.One2many('biblio.room.booking', 'room_id', string='Réservations')

    # Nombre de réservations : champ CALCULÉ (pas de colonne en base), affiché dans le bouton intelligent.
    booking_count = fields.Integer('Nombre de réservations', compute='_compute_booking_count')

    # Le calcul est relancé quand la liste des réservations de la salle change.
    @api.depends('booking_ids')
    # Méthode de calcul : self peut contenir plusieurs salles.
    def _compute_booking_count(self):
        # On traite les salles une par une.
        for room in self:
            # len() compte les réservations liées à cette salle.
            room.booking_count = len(room.booking_ids)

    # Méthode appelée par le bouton intelligent (type="object" dans la vue).
    def action_view_bookings(self):
        # Vérifie qu'on travaille sur UNE seule salle (sinon erreur).
        self.ensure_one()
        # Renvoie une action de fenêtre : Odoo l'ouvre comme un menu.
        return {
            # Type d'action : ouvrir des vues sur un modèle.
            'type': 'ir.actions.act_window',
            # Titre affiché en haut de la liste (et dans le fil d'Ariane).
            'name': 'Réservations',
            # Le modèle à afficher : les réservations.
            'res_model': 'biblio.room.booking',
            # Vues proposées : la liste d'abord, puis le formulaire.
            'view_mode': 'list,form',
            # Filtre : seulement les réservations de CETTE salle.
            'domain': [('room_id', '=', self.id)],
            # Valeur par défaut : une réservation créée depuis cette liste aura déjà cette salle.
            'context': {'default_room_id': self.id},
        }


# =====================================================================
# Modèle « Réservation d'une salle »
# =====================================================================
# Classe Python qui devient le modèle biblio.room.booking (table biblio_room_booking).
class BiblioRoomBooking(models.Model):
    # Nom technique du modèle.
    _name = 'biblio.room.booking'
    # Description lisible du modèle.
    _description = "Réservation d'une salle"
    # Tri par défaut : les réservations les plus récentes en premier.
    _order = 'start_date desc'

    # La salle réservée : plusieurs réservations → une salle (Many2one), obligatoire.
    room_id = fields.Many2one('biblio.room', string='Salle', required=True)
    # Nom de la personne ou du groupe qui réserve, obligatoire.
    customer = fields.Char('Réservé par', required=True)
    # Date de début, obligatoire, aujourd'hui par défaut.
    start_date = fields.Date('Début', required=True, default=fields.Date.context_today)
    # Date de fin, obligatoire.
    end_date = fields.Date('Fin', required=True)
    # Montant de la caution.
    deposit = fields.Float('Caution')

    # Prix par jour : champ LIÉ (related). Il lit room_id.daily_price, sans le recopier en base.
    daily_price = fields.Float('Prix par jour', related='room_id.daily_price')
    # Durée en jours : champ CALCULÉ, non stocké (recalculé à chaque lecture).
    duration = fields.Integer('Durée (jours)', compute='_compute_duration')
    # Prix total : champ CALCULÉ et STOCKÉ (store=True) → colonne en base, on peut trier et totaliser.
    total_price = fields.Float('Prix total', compute='_compute_total_price', store=True)

    # La durée dépend des deux dates.
    @api.depends('start_date', 'end_date')
    # Méthode de calcul de la durée.
    def _compute_duration(self):
        # On traite les réservations une par une.
        for booking in self:
            # Si les deux dates sont remplies…
            if booking.start_date and booking.end_date:
                # … soustraire deux dates donne un timedelta ; .days = nombre de jours d'écart.
                # + 1 car début et fin sont compris : du 10 au 12 → 2 jours d'écart + 1 = 3 jours.
                # max(0, …) évite une durée négative si la fin est avant le début.
                booking.duration = max(0, (booking.end_date - booking.start_date).days + 1)
            # Sinon (une date manque)…
            else:
                # … la durée vaut 0 (un compute doit TOUJOURS donner une valeur).
                booking.duration = 0

    # Le total dépend des dates ET du prix de la salle : avec store=True, il faut TOUT lister,
    # sinon la valeur en base reste figée. 'room_id.daily_price' suit la relation : si le prix
    # de la salle change, le total de toutes ses réservations est recalculé.
    @api.depends('start_date', 'end_date', 'room_id.daily_price')
    # Méthode de calcul du prix total.
    def _compute_total_price(self):
        # On traite les réservations une par une.
        for booking in self:
            # Total = durée × prix par jour (duration est recalculée d'abord par Odoo).
            booking.total_price = booking.duration * booking.room_id.daily_price

    # Le nom affiché dépend du nom de la salle et de la date de début.
    @api.depends('room_id.name', 'start_date')
    # En Odoo 17+ (donc 19), on surcharge _compute_display_name pour changer le nom affiché.
    def _compute_display_name(self):
        # On traite les réservations une par une.
        for booking in self:
            # Date au format belge 10/10/2026 ; chaîne vide si la date n'est pas encore remplie.
            date = booking.start_date.strftime('%d/%m/%Y') if booking.start_date else ''
            # Nom de la salle ; chaîne vide si aucune salle n'est choisie (nouvelle réservation).
            room = booking.room_id.name or ''
            # Assemble le texte : « Réservation Salle Yourcenar – 10/10/2026 ».
            booking.display_name = f"Réservation {room} – {date}"

    # Se déclenche dans le FORMULAIRE, dès que l'utilisateur choisit ou change la salle.
    @api.onchange('room_id')
    # Méthode onchange : self = la réservation en cours de saisie (pas encore enregistrée).
    def _onchange_room_id(self):
        # On propose une caution de 2 × le prix par jour de la salle choisie.
        # (si aucune salle : daily_price vaut 0, donc caution 0). L'utilisateur peut la modifier ensuite.
        self.deposit = 2 * self.room_id.daily_price
