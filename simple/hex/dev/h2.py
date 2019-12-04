# hex player              RBH 2016
# style influenced by 
#   * Michi (by Petr Baudis)
#   * Morat (by Timo Ewalds)
#   * Miaowy (by RBH)
#   * Benzene (by 
#       Broderick Arneson, Philip Henderson, Jakub Pawlewicz,
#       Aja Huang, Yngvi Bjornsson, Michael Johanson, Morgan Kan,
#       Kenny Young, Noah Weninger, RBH)
# boardsize constraint: 
#    fat board should fit in dtype uint8
#    for larger boards, increase parent dtype to uint16

import numpy as np
from copy import deepcopy
from random import shuffle, choice
import math

class Cell: #############  cells #########################
  e,b,w,ch = 0,1,2, '.*@'       # empty, black, white

  def get_ptm(ch):
    return ord(ch) >> 5 # divide by the floor of 32 get player 1 or 2 based on char * or @

  def opponent(c):
    return 3-c

class B: ################ the board #######################

  # 2x3 naked  1 guard layer   2 " "

  #                           *******
  #            *****           *******
  #    ...      o...o           oo...oo
  #     ...      o...o           oo...oo
  #               *****           *******
  #                                *******

  # naked        row col       positions
  
  #    ...      0 0  0 1  0 2     0  1  2
  #     ...      1 0  1 1  1 2     3  4  5
  
  # fat           row col                 positions
  
  #  -***-     -1-1 -1 0 -1 1 -1 2 -1 3    0  1  2  3  4
  #   o...o     0-1   0 0  0 1  0 2  0 3    5  6  7  8  9
  #    o...o     1-1   1 0  1 1  1 2  1 3   10 11 12 13 14
  #     -***-     2-1   2 0  2 1  2 2  2 3   15 16 17 18 19

  def __init__(self,rows,cols):
    B.r  = rows  
    B.c  = cols
    B.n  = rows*cols   # number cells
    B.g  = 1   # number guard layers that encircle true board
    B.w  = B.c + B.g + B.g  # width of layered board
    B.h  = B.r + B.g + B.g
    B.fat_n = B.h * B.w # fat-board cells

    B.nbr_offset = (-B.w, -B.w+1, 1, B.w, B.w-1, -1)
    #   0 1
    #  5 . 2
    #   4 3

    B.border = (  # on fat board, location of cell on these borders:
      0,                    # top 
      B.fat_n - 1,          # btm 
      B.g*B.w,              # white left
      (1+B.g)*B.w - 1)

    B.empty_brd = np.array([0]*self.n, dtype=np.uint8)
    B.empty_fat_brd = np.array(
      ([Cell.b]*self.w) * self.g +
      ([Cell.w]*self.g + [0]*self.c + [Cell.w]*self.g) * self.r +
      ([Cell.b]*self.w) * self.g, dtype=np.uint8)

    # parent: for union find   is_root(x): return parent[x] == x
    B.parent = np.array([0]*B.fat_n, dtype=np.uint8)
    p = 0
    for fr in range(B.h):
      for fc in range(B.w):
        if fr < B.g:         B.parent[p] = B.border[0] # top
        elif fr >= B.g + B.r: B.parent[p] = B.border[1] # btm
        elif fc < B.g:       B.parent[p] = B.border[2] # left
        elif fc >= B.g + B.c: B.parent[p] = B.border[3] # right
        else:                B.parent[p] = p
        p += 1

##### board i-o

  letters = 'abcdefghijklmnopqrstuvwxyz'
  esc       = '\033['            ###### these are for colors
  endcolor  =  esc + '0m'
  textcolor =  esc + '0;37m'
  color_of  = (textcolor, esc + '0;35m', esc + '0;32m')
  
def disp(brd):   # convert board to string picture
  if len(brd)==B.n:  # true board: add outer layers
    s = 2*' ' + ' '.join(B.letters[0:B.c]) + '\n'
    for j in range(B.r):
      s += j*' ' + '{:2d}'.format(j+1) + ' ' + \
        ' '.join([Cell.ch[brd[k + j*B.c]] for k in \
        range(B.c)]) + ' ' + Cell.ch[Cell.w] + '\n'
    return s + (3+B.r)*' ' + ' '.join(Cell.ch[Cell.b]*B.c) + '\n'

  elif len(brd)==B.fat_n: # fat board: just return cells
    s = ''
    for j in range(B.h):
      s += j*' ' + ' '.join([Cell.ch[brd[k + j*B.w]] \
        for k in range(B.w)]) + '\n'
    return s
  else: assert(False)
     
def show_board(brd):
  print('')
  print(paint(disp(brd)))

def disp_parent(parent):  # convert parent to string picture
  psn, s = 0, ''
  for fr in range(B.h):
    s += fr*' ' + ' '.join([
    #      ('{:3d}'.format(parent[psn+k]))     \
           ('  *' if parent[psn+k]==psn+k else \
            '{:3d}'.format(parent[psn+k]))     \
           for k in range(B.w)]) + '\n'
    psn += B.w
  return s

def show_parent(P):
  print(disp_parent(P))

############ colored output ######################

def paint(s):  # replace with colored characters
  p = ''
  for c in s:
    x = Cell.ch.find(c)
    if x >= 0:
      p += B.color_of[x] + c + B.endcolor
    elif c.isalnum():
      p += B.textcolor + c + B.endcolor
    else: p += c
  return p

######## positions <------>   row, column coordinates

def psn_of(x,y):
  return x*B.c + y

def fat_psn_of(x,y):
  return (x+ B.g)*B.w + y + B.g

def rc_of(p): # return usual row, col coordinates
  return divmod(p, B.c)

def rc_of_fat(p):  # return usual row, col coordinates
  x,y = divmod(p, B.w)
  return x - B.g, y - B.g

### mcts ########################################

def legal_moves(board):
  L = []
  for psn in range(B.fat_n):
    if board[psn] == Cell.e:
      L.append(psn)
  return L

class Mcts_node:
  def __init__(self, move, parent, depth=0): # move is from parent to node
    self.depth, self.move, self.parent, self.children = depth, move, parent, []
    self.wins, self.visits, self.rave_wins, self.rave_visits = 0, 0, 0, 0

  def tree_policy_child(self, parity):
    if self.is_leaf():
      return self
    if parity == 0: # max node
      best = max([win_ratio(j.wins, j.visits, j.rave_wins, j.rave_visits) for j in self.children])
    else:
      best = min([win_ratio(j.wins, j.visits, j.rave_wins, j.rave_visits) for j in self.children])
    return self.children[choice([j
      for j,child_node in enumerate(self.children) \
                                 if win_ratio(
                                              child_node.wins,
                                              child_node.visits,
                                              child_node.rave_wins,
                                              child_node.rave_visits
                                              ) == best])]

  def expand_node(self, board):
    if self.children != []: #can only expand node once
      return
    for m in legal_moves(board):
      self.children.append(Mcts_node(m, self, self.depth+1))

  def is_leaf(self):
    return self.children == []

  def has_parent(self):
    return self.parent is not None

  def update(self, root_ptm, winner):
    self.visits += 1
    if winner == root_ptm:
      self.wins += 1

  def rave_update(self, root_ptm, winner,rave_moves):
    self.visits += 1
    if winner == root_ptm:
      self.wins += 1
    if winner in rave_moves:
      for child in self.children:
        if child.move in rave_moves[winner]:
          child.rave_visits += 1
          if winner == root_ptm:
              child.rave_wins += 1
        elif child.move in rave_moves[Cell.opponent(winner)]:
          child.rave_visits += 1

def win_ratio(w,v,rw,rv):
  wn = (w+5) / (v+10)
  wnrave = (rw+5) / (rv+10)
  #beta = (rv) / ( ( v + rv + 4*v*rv )+10 )
  k = 500
  beta = k/(k+v)
  return (1-beta)*wn + (beta*wnrave) + 0.5 * math.sqrt(math.log(rv+20)/(v+10))

def simulate(brd, rave_table, uf_p, ptm):
  b, P, L, m = deepcopy(brd), deepcopy(uf_p), legal_moves(brd), ptm
  shuffle(L)
  #print(L)
  for psn in L:
    rave_putstone_and_update(b, rave_table, P, psn, m)
   # show_board(b)
    if win_check(P, m):
      return m
    m = Cell.opponent(m)

def sim_test(brd, uf_p, ptm, sims):
  print('\nsim test\n')
  rave_table = {}
  iteration, wins = 0, 0
  while iteration < sims:
    iteration += 1
    if ptm == simulate(brd, rave_table, uf_p, ptm):
      wins += 1
  print(Cell.ch[ptm], ' to play', wins, '/', sims, 'wins')

def rave_sim_test(brd, rave_table, uf_p, ptm, sims):
  print('\nsim test\n')
  iteration, wins = 0, 0
  while iteration < sims:
    iteration += 1
    if ptm == simulate(brd, rave_table, uf_p, ptm):
      wins += 1
  print(Cell.ch[ptm], ' to play', wins, '/', sims, 'wins')

def mcts(board, uf_parents, root_ptm, max_iterations, expand_threshold):
  def descend(node, board, ptm, uf_par, rave_table):
    node = node.tree_policy_child(root_ptm - ptm)
    rave_putstone_and_update(board, rave_table, uf_par, node.move, ptm)
    return node, board, Cell.opponent(ptm)

  root_node, iterations = Mcts_node('root', None, 0), 0
  root_node.expand_node(board)
  ptm = root_ptm
  while iterations < max_iterations:
    rave_table = {}
    node, ptm = root_node, root_ptm
    brd, uf_par = deepcopy(board), deepcopy(uf_parents)

    while not node.is_leaf():            # select leaf
      node, brd, ptm = descend(node, brd, ptm, uf_par, rave_table)

    if node.visits > expand_threshold and (not win_check(uf_par, ptm)):
      node.expand_node(brd)              # expand
      node, brd, ptm = descend(node, brd, ptm, uf_par, rave_table)

    result = simulate(brd, rave_table, uf_par, ptm)  # simulate
    while True:             # propagate
      node.rave_update(root_ptm, result, rave_table)
      node = node.parent
      if not node.has_parent():
        node.rave_update(root_ptm, result, rave_table)
        break
    iterations += 1
  return root_node.tree_policy_child(root_ptm-ptm).move

### connectivity ################################
###   want win_check after each move, so union find

class UF:        # union find

  def union(parent,x,y):  
    parent[x] = y
    return y

  def find(parent,x): # using grandparent compression
    while True:
      px = parent[x]
      if x == px: return x
      gx = parent[px]
      if px == gx: return px
      parent[x], x = gx, gx

#class D2:  # 2-distance
      
def win_check(P, color):
  if color == Cell.b:
    return UF.find(P, B.border[0]) == UF.find(P, B.border[1])
  return UF.find(P, B.border[2]) == UF.find(P, B.border[3])
      
### user i-o

def tst(r,c):
  B(r,c)
  print(disp(B.empty_brd))
  print(paint(disp(B.empty_brd)))
  print(disp(B.empty_fat_brd))
  print(paint(disp(B.empty_fat_brd)))
  print(disp_parent(B.parent))

  for r in range(B.r):
    for c in range(B.c):
      p = psn_of(r,c)
      print('{:3}'.format(p), end='')
      assert (r,c) == rc_of(p)
    print('')

  for r in range(-B.g, B.r + B.g):
    for c in range(-B.g, B.c + B.g):
      p = fat_psn_of(r,c)
      #print(r,c,p,B.rc_of_fat(p))
      print('{:3}'.format(p), end='')
      assert (r,c) == (rc_of_fat(p))
    print('')

  f, (a,b,c,d) = B.empty_fat_brd, B.border
  assert(f[a] == Cell.b and f[b] == Cell.b)
  assert(f[c] == Cell.w and f[d] == Cell.w)
  print(B.r, B.c, 'borders',a,b,c,d)

def big_tst():
  for j in range(1,6):
    for k in range(1,10):
      tst(j,k)

## consider all possible isomorphic positions, return min
#def min_iso(L): # using numpy array indexing here
  #return min([brd_to_int( L[Isos[j]] ) for j in range(8)])

# convert from integer for board position
#def base_3( y ): 
#  assert(y <= ttt_states)
#  L = [0]*Cell.n
#  for j in range(Cell.n):
#    y, L[j] = divmod(y,3)
#    if y==0: break
#  return np.array( L, dtype = np.int16)

# input-output ################################################
#def char_to_cell(c): 
#  return Cell.ch.index(c)

def genmoverequest(cmd):
  cmd = cmd.split()
  invalid = (False, None, '\n invalid genmove request\n')
  if len(cmd)==2:
    x = Cell.ch.find(cmd[1][0])
    if x == 1 or x == 2:
      return True, cmd[1][0], ''
  return invalid

def empty_cells(brd):
  L = []
  for j in range(B.fat_n):
    if brd[j] == Cell.e: 
      L.append(j)
  return L

def flat_mc_move(brd, P, color):
# coming soon
  pass
  #for c in shuffle(empty_cells(brd)):

def parent_update(brd, P, psn, color):
# update parent-structure after move color --> psn
  captain = UF.find(P, psn)
  for j in range(6):  # 6 neighbours
    nbr = psn + B.nbr_offset[j]
    if color == brd[nbr]:
      nbr_root = UF.find(P, nbr)
      captain = UF.union(P, captain, nbr_root)

def putstone(brd, p, cell):
  brd[p] = cell

def putstone_and_update(brd, P, psn, color):
  putstone(brd, psn, color)
  parent_update(brd, P, psn, color)

def rave_putstone_and_update(brd, rave_table, P, psn, color):
  def play_while_tracking_rave_moves(action):
    if color not in rave_table:
      rave_table[color] = {}
    if action not in rave_table[color]:
      rave_table[color][action] = True

  putstone_and_update(brd, P, psn, color)
  play_while_tracking_rave_moves(psn)

def undo(H, brd):  # pop last location, erase that cell
  if len(H)==0:
    print('\n    nothing to undo\n')
  else:
    lcn = H.pop()
    brd[lcn] = Cell.e

def make_move(brd, P, cmd, H):
    parseok, cmd = False, cmd.split()
    if len(cmd)==2:
      color = Cell.ch.find(cmd[0][0])
      if color >= 0:
        q, n = cmd[1][0], cmd[1][1:]
        if q.isalpha() and n.isdigit():
          x, y = int(n) - 1, ord(q)-ord('a')
          if x>=0 and x < B.r and y>=0 and y < B.c:
            psn = fat_psn_of(x,y)
            if brd[psn] != Cell.e:
              print('\n cell already occupied\n')
              return
            else:   
              #putstone(brd, psn, color)
              #parent_update(brd, P, psn, color)
              putstone_and_update(brd, P, psn, color)
              H.append(psn) # add location to history
              if win_check(P, color): print(' win: game over')
              return
          else: 
            print('\n  coordinate off board\n')
            return
    print('\n  make_move did not parse \n')

def act_on_request(board, P, history):
  cmd = input(' ')

  if len(cmd) == 0:
    return False, '\n ... adios :)\n'

  elif cmd[0][0] =='h':
    return True, '\n' +\
      ' * b2       play b b 2\n' +\
      ' @ e3       play w e 3\n' +\
      ' g b/w         genmove\n' +\
      ' u                undo\n' +\
      ' [return]         quit\n'

  elif cmd[0][0] =='?':
    return True, '\n  coming soon\n'

  elif cmd[0][0] =='u':
    undo(history, board)
    return True, '\n  undo\n'

  elif cmd[0][0] =='g':
    cmd = cmd.split()
    if (len(cmd) == 2) and (cmd[1][0] in Cell.ch):
      ptm = Cell.get_ptm(cmd[1][0])
      psn = mcts(board, P, ptm, 10000, 1)
      putstone_and_update(board, P, psn, ptm)
      history.append(psn)  # add location to history
      if win_check(P, ptm): print(' win: game over')
    else:
      return True, '\n did not give a valid player\n'
    return True, '\n  gen move with mcts\n'

  elif (cmd[0][0] in Cell.ch):
    make_move(board, P, cmd, history)
    return True, '\n  make_move\n'

  else:
    return True, '\n  unable to parse request\n'

def interact():
  Board = B(4,4)
  board, history = deepcopy(Board.empty_fat_brd), []
  P = deepcopy(Board.parent)
  while True:
    show_board(board)
    print('legal ', legal_moves(board),'\n')
    show_parent(P)
    #sim_test(board, P, Cell.b, 10000)
    #sim_test(board, P, Cell.w, 10000)
    ok, msg = act_on_request(board, P, history)
    print(msg)
    if not ok:
      return

#big_tst()
interact()
